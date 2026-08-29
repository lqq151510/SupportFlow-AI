package com.lqq.supportflow;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatIllegalArgumentException;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.lqq.supportflow.model.domain.ModelProtocol;
import com.lqq.supportflow.model.infrastructure.persistence.ModelConfigEntity;
import com.lqq.supportflow.model.infrastructure.persistence.ModelConfigMapper;
import com.lqq.supportflow.model.infrastructure.persistence.ModelUsageEntity;
import com.lqq.supportflow.model.infrastructure.persistence.ModelUsageMapper;
import com.lqq.supportflow.model.infrastructure.persistence.MyBatisModelConfigAdapter;
import com.lqq.supportflow.model.infrastructure.persistence.MyBatisModelUsageAdapter;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

class MyBatisModelPersistenceAdapterTest {

    @Test
    void savesAndUpdatesModelConfigWithoutReplacingBlankOptionalValues() {
        ModelConfigMapper mapper = mock(ModelConfigMapper.class);
        MyBatisModelConfigAdapter adapter = new MyBatisModelConfigAdapter(mapper);

        adapter.save(7L, "主聊天模型", ModelProtocol.OPENAI_COMPATIBLE, "https://api.example/v1",
                "chat-v1", "ciphertext", true, true);
        ArgumentCaptor<ModelConfigEntity> saved = ArgumentCaptor.forClass(ModelConfigEntity.class);
        verify(mapper).insert(saved.capture());
        assertThat(saved.getValue())
                .extracting(entity -> entity.tenantId, entity -> entity.protocol, entity -> entity.isDefault,
                        entity -> entity.isKnowledgeDefault)
                .containsExactly(7L, "OPENAI_COMPATIBLE", true, true);

        ModelConfigEntity existing = modelConfig(9L, 7L, "旧名称", "ANTHROPIC", "https://old", "claude", false, false);
        when(mapper.selectOne(any())).thenReturn(existing);
        var updated = adapter.update(7L, 9L, "  新名称  ", ModelProtocol.OPENAI_COMPATIBLE, "  https://new/v1  ",
                "  new-chat  ", "new-ciphertext", true, true);

        assertThat(updated.name()).isEqualTo("新名称");
        assertThat(updated.protocol()).isEqualTo(ModelProtocol.OPENAI_COMPATIBLE);
        assertThat(updated.baseUrl()).isEqualTo("https://new/v1");
        assertThat(updated.modelName()).isEqualTo("new-chat");
        assertThat(updated.isDefault()).isTrue();
        assertThat(updated.isKnowledgeDefault()).isTrue();

        existing.name = "保留名称";
        existing.baseUrl = "https://keep";
        existing.modelName = "keep-chat";
        adapter.update(7L, 9L, " ", null, " ", " ", " ", false, false);
        assertThat(existing.name).isEqualTo("保留名称");
        assertThat(existing.baseUrl).isEqualTo("https://keep");
        assertThat(existing.modelName).isEqualTo("keep-chat");
        verify(mapper, times(6)).update(any(), any());
    }

    @Test
    void scopesDefaultSelectionAndFindersToTheCurrentTenant() {
        ModelConfigMapper mapper = mock(ModelConfigMapper.class);
        MyBatisModelConfigAdapter adapter = new MyBatisModelConfigAdapter(mapper);
        ModelConfigEntity defaultConfig = modelConfig(3L, 7L, "默认", "OPENAI_COMPATIBLE", "https://api", "chat", false, false);
        when(mapper.selectOne(any())).thenReturn(defaultConfig);

        assertThat(adapter.setDefault(7L, 3L).isDefault()).isTrue();
        assertThat(adapter.setKnowledgeDefault(7L, 3L).isKnowledgeDefault()).isTrue();
        verify(mapper, times(4)).update(any(), any());

        when(mapper.selectList(any())).thenReturn(List.of(defaultConfig));
        assertThat(adapter.list(7L)).singleElement().extracting(config -> config.id()).isEqualTo(3L);
        assertThat(adapter.findDefaultEmbedding(7L)).get().extracting(config -> config.modelName()).isEqualTo("chat");
        assertThat(adapter.findDefaultChat(7L)).get().extracting(config -> config.protocol()).isEqualTo(ModelProtocol.OPENAI_COMPATIBLE);

        when(mapper.selectOne(any())).thenReturn(null, defaultConfig);
        assertThat(adapter.findDefaultKnowledge(7L)).get().extracting(config -> config.modelName()).isEqualTo("chat");

        when(mapper.selectOne(any())).thenReturn((ModelConfigEntity) null);
        assertThatIllegalArgumentException().isThrownBy(() -> adapter.setDefault(7L, 3L))
                .withMessage("model configuration does not belong to tenant");
    }

    @Test
    void storesUsageAndSummarizesMissingOptionalColumnsSafely() {
        ModelUsageMapper mapper = mock(ModelUsageMapper.class);
        MyBatisModelUsageAdapter adapter = new MyBatisModelUsageAdapter(mapper);

        adapter.save(7L, "CHAT", "deepseek-chat", "OPENAI_COMPATIBLE", 100, 40, 250,
                new BigDecimal("0.1200"), new BigDecimal("0.0160"));
        ArgumentCaptor<ModelUsageEntity> saved = ArgumentCaptor.forClass(ModelUsageEntity.class);
        verify(mapper).insert(saved.capture());
        assertThat(saved.getValue().totalTokens).isEqualTo(140);

        ModelUsageEntity complete = usage(1L, 7L, "CHAT", "deepseek-chat", 100, 40, 140, 250L,
                new BigDecimal("0.1200"), new BigDecimal("0.0160"));
        ModelUsageEntity legacy = usage(2L, 7L, null, null, null, null, null, null, null, null);
        when(mapper.selectList(any())).thenReturn(List.of(complete, legacy));

        assertThat(adapter.listRecent(7L, 0)).hasSize(2);
        var stats = adapter.getStatistics(7L);
        assertThat(stats.totalCalls()).isEqualTo(2);
        assertThat(stats.totalInputTokens()).isEqualTo(100);
        assertThat(stats.totalOutputTokens()).isEqualTo(40);
        assertThat(stats.totalTokens()).isEqualTo(140);
        assertThat(stats.averageLatencyMs()).isEqualTo(125);
        assertThat(stats.totalEstimatedCostCny()).isEqualByComparingTo("0.1200");
        assertThat(stats.scenarioCalls()).containsEntry("CHAT", 1L).containsEntry("OTHER", 1L);
        assertThat(stats.modelTokens()).containsEntry("deepseek-chat", 140L).containsEntry("unknown", 0L);
        assertThat(stats.modelCostCny()).containsEntry("unknown", BigDecimal.ZERO);
    }

    private ModelConfigEntity modelConfig(Long id, Long tenantId, String name, String protocol, String baseUrl,
                                          String modelName, boolean isDefault, boolean isKnowledgeDefault) {
        ModelConfigEntity entity = new ModelConfigEntity();
        entity.id = id;
        entity.tenantId = tenantId;
        entity.name = name;
        entity.protocol = protocol;
        entity.baseUrl = baseUrl;
        entity.modelName = modelName;
        entity.encryptedApiKey = "ciphertext";
        entity.isDefault = isDefault;
        entity.isKnowledgeDefault = isKnowledgeDefault;
        entity.createdAt = Instant.now();
        entity.updatedAt = entity.createdAt;
        return entity;
    }

    private ModelUsageEntity usage(Long id, Long tenantId, String scenario, String modelName, Integer input,
                                   Integer output, Integer total, Long latency, BigDecimal cny, BigDecimal usd) {
        ModelUsageEntity entity = new ModelUsageEntity();
        entity.id = id;
        entity.tenantId = tenantId;
        entity.scenario = scenario;
        entity.modelName = modelName;
        entity.protocol = "OPENAI_COMPATIBLE";
        entity.inputTokens = input;
        entity.outputTokens = output;
        entity.totalTokens = total;
        entity.latencyMs = latency;
        entity.estimatedCostCny = cny;
        entity.estimatedCostUsd = usd;
        entity.createdAt = Instant.now();
        return entity;
    }
}
