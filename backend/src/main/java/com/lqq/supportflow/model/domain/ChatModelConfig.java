package com.lqq.supportflow.model.domain;

public record ChatModelConfig(ModelProtocol protocol, String baseUrl, String modelName, String encryptedApiKey) { }
