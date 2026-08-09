package com.lqq.supportflow.model.domain;

public record ModelConfig(Long id, String name, ModelProtocol protocol, String baseUrl, String modelName, boolean isDefault) { }
