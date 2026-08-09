package com.lqq.supportflow.model.domain;

import java.util.List;

public record ChatModelRequest(Long tenantId, List<ChatMessage> messages, List<ToolDefinition> tools) {

    public record ChatMessage(String role, String content) { }
    public record ToolDefinition(String name, String description, java.util.Map<String, Object> inputSchema) { }
}
