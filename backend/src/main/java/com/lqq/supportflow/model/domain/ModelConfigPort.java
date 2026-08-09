package com.lqq.supportflow.model.domain;

public interface ModelConfigPort { ModelConfig save(Long tenantId, String name, ModelProtocol protocol, String baseUrl, String modelName, String encryptedApiKey, boolean isDefault); }
