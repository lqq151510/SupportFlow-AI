package com.lqq.supportflow.model.domain;

public record ModelConfig(@com.fasterxml.jackson.databind.annotation.JsonSerialize(using=com.fasterxml.jackson.databind.ser.std.ToStringSerializer.class) Long id, String name, ModelProtocol protocol, String baseUrl, String modelName, boolean isDefault) { }
