package com.lqq.supportflow.model.domain;

import java.util.List;
import java.util.Optional;

public interface ModelConfigPort {
    ModelConfig save(Long tenantId, String name, ModelProtocol protocol, String baseUrl, String modelName, String encryptedApiKey, boolean isDefault, boolean isKnowledgeDefault);

    default ModelConfig save(Long tenantId, String name, ModelProtocol protocol, String baseUrl, String modelName, String encryptedApiKey, boolean isDefault) {
        return save(tenantId, name, protocol, baseUrl, modelName, encryptedApiKey, isDefault, false);
    }

    ModelConfig update(Long tenantId, Long modelConfigId, String name, ModelProtocol protocol, String baseUrl, String modelName, String encryptedApiKeyOrNull, Boolean isDefault, Boolean isKnowledgeDefault);

    ModelConfig setDefault(Long tenantId, Long modelConfigId);

    ModelConfig setKnowledgeDefault(Long tenantId, Long modelConfigId);

    List<ModelConfig> list(Long tenantId);

    Optional<EmbeddingModelConfig> findDefaultEmbedding(Long tenantId);

    Optional<ChatModelConfig> findDefaultChat(Long tenantId);

    Optional<ChatModelConfig> findDefaultKnowledge(Long tenantId);
}
