package com.lqq.supportflow.model.domain;

import java.util.List;

public record ChatModelRequest(Long tenantId, List<ChatMessage> messages) {

    public record ChatMessage(String role, String content) { }
}
