package com.lqq.supportflow.model.domain;
import java.util.Optional;
public interface ModelConfigPort { ModelConfig save(Long tenantId, String name, ModelProtocol protocol, String baseUrl, String modelName, String encryptedApiKey, boolean isDefault); Optional<EmbeddingModelConfig> findDefaultEmbedding(Long tenantId); Optional<ChatModelConfig> findDefaultChat(Long tenantId); }
