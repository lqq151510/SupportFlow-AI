package com.lqq.supportflow.conversation;
public record HandoffRequiredEvent(Long tenantId,Long customerId,Long conversationId,Long generationId,String reason) { }
