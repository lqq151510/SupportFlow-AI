package com.lqq.supportflow;

import static org.junit.jupiter.api.Assertions.*;

import com.lqq.supportflow.model.application.UpdateModelConfigService;
import com.lqq.supportflow.model.domain.*;
import java.util.*;
import org.junit.jupiter.api.Test;

class UpdateModelConfigServiceTest {

    static class MockModelConfigPort implements ModelConfigPort {
        private final Map<Long, ModelConfig> configs = new HashMap<>();

        @Override
        public ModelConfig save(Long tenantId, String name, ModelProtocol protocol, String baseUrl, String modelName, String encryptedApiKey, boolean isDefault, boolean isKnowledgeDefault) {
            ModelConfig config = new ModelConfig(1L, name, protocol, baseUrl, modelName, isDefault, isKnowledgeDefault);
            configs.put(1L, config);
            return config;
        }

        @Override
        public ModelConfig update(Long tenantId, Long modelConfigId, String name, ModelProtocol protocol, String baseUrl, String modelName, String encryptedApiKeyOrNull, Boolean isDefault, Boolean isKnowledgeDefault) {
            ModelConfig existing = configs.get(modelConfigId);
            ModelConfig updated = new ModelConfig(
                    modelConfigId,
                    name != null ? name : existing.name(),
                    protocol != null ? protocol : existing.protocol(),
                    baseUrl != null ? baseUrl : existing.baseUrl(),
                    modelName != null ? modelName : existing.modelName(),
                    isDefault != null ? isDefault : existing.isDefault(),
                    isKnowledgeDefault != null ? isKnowledgeDefault : existing.isKnowledgeDefault()
            );
            configs.put(modelConfigId, updated);
            return updated;
        }

        @Override public ModelConfig setDefault(Long tenantId, Long modelConfigId) { return null; }
        @Override public ModelConfig setKnowledgeDefault(Long tenantId, Long modelConfigId) { return null; }
        @Override public List<ModelConfig> list(Long tenantId) { return new ArrayList<>(configs.values()); }
        @Override public Optional<EmbeddingModelConfig> findDefaultEmbedding(Long tenantId) { return Optional.empty(); }
        @Override public Optional<ChatModelConfig> findDefaultChat(Long tenantId) { return Optional.empty(); }
        @Override public Optional<ChatModelConfig> findDefaultKnowledge(Long tenantId) { return Optional.empty(); }
    }

    static class MockModelSecretPort implements ModelSecretPort {
        @Override public String encrypt(String raw) { return "ENC:" + raw; }
        @Override public String decrypt(String enc) { return enc.replace("ENC:", ""); }
    }

    @Test
    void updatesModelConfigInPlace() {
        MockModelConfigPort port = new MockModelConfigPort();
        port.save(1L, "初始模型", ModelProtocol.OPENAI_COMPATIBLE, "https://api.openai.com/v1", "gpt-4o", "secret", true, false);

        UpdateModelConfigService service = new UpdateModelConfigService(port, new MockModelSecretPort(), url -> {});
        ModelConfig updated = service.update(1L, 1L, "DeepSeek 主模型", ModelProtocol.OPENAI_COMPATIBLE, "https://api.deepseek.com/v1", "deepseek-chat", "new-secret", true, true);

        assertEquals("DeepSeek 主模型", updated.name());
        assertEquals("https://api.deepseek.com/v1", updated.baseUrl());
        assertEquals("deepseek-chat", updated.modelName());
        assertTrue(updated.isDefault());
        assertTrue(updated.isKnowledgeDefault());
    }
}
