package com.lqq.supportflow.conversation;

public record GenerationRequestedEvent(Long tenantId, Long customerId, Long conversationId, Long generationId, String content) { }
