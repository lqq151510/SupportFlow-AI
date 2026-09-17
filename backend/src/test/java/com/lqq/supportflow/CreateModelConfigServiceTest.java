package com.lqq.supportflow;

import static org.junit.jupiter.api.Assertions.assertTrue;

import com.lqq.supportflow.model.application.CreateModelConfigService;
import com.lqq.supportflow.model.domain.ChatModelConfig;
import com.lqq.supportflow.model.domain.EmbeddingModelConfig;
import com.lqq.supportflow.model.domain.ModelConfig;
import com.lqq.supportflow.model.domain.ModelConfigPort;
import com.lqq.supportflow.model.domain.ModelProtocol;
import com.lqq.supportflow.model.domain.ModelSecretPort;
import java.util.List;
import java.util.Optional;
import org.junit.jupiter.api.Test;

class CreateModelConfigServiceTest {

    @Test
    void persistsKnowledgeDefaultFlagWhenCreatingModel() {
        CapturingModelConfigPort port = new CapturingModelConfigPort();
        CreateModelConfigService service = new CreateModelConfigService(port, new ModelSecretPort() {
            @Override public String encrypt(String raw) { return "encrypted:" + raw; }
            @Override public String decrypt(String encrypted) { return encrypted; }
        }, value -> { });

        ModelConfig result = service.create(7L, "知识整理模型", ModelProtocol.OPENAI_COMPATIBLE,
                "https://api.deepseek.com/v1", "deepseek-chat", "secret", true, true);

        assertTrue(result.isDefault());
        assertTrue(result.isKnowledgeDefault());
        assertTrue(port.knowledgeDefault);
    }

    private static final class CapturingModelConfigPort implements ModelConfigPort {
        private boolean knowledgeDefault;

        @Override
        public ModelConfig save(Long tenantId, String name, ModelProtocol protocol, String baseUrl,
                                String modelName, String encryptedApiKey, boolean isDefault, boolean isKnowledgeDefault) {
            knowledgeDefault = isKnowledgeDefault;
            return new ModelConfig(1L, name, protocol, baseUrl, modelName, isDefault, isKnowledgeDefault);
        }

        @Override public ModelConfig update(Long tenantId, Long modelConfigId, String name, ModelProtocol protocol,
                                            String baseUrl, String modelName, String encryptedApiKeyOrNull,
                                            Boolean isDefault, Boolean isKnowledgeDefault) { return null; }
        @Override public ModelConfig setDefault(Long tenantId, Long modelConfigId) { return null; }
        @Override public ModelConfig setKnowledgeDefault(Long tenantId, Long modelConfigId) { return null; }
        @Override public List<ModelConfig> list(Long tenantId) { return List.of(); }
        @Override public Optional<EmbeddingModelConfig> findDefaultEmbedding(Long tenantId) { return Optional.empty(); }
        @Override public Optional<ChatModelConfig> findDefaultChat(Long tenantId) { return Optional.empty(); }
        @Override public Optional<ChatModelConfig> findDefaultKnowledge(Long tenantId) { return Optional.empty(); }
    }
}
