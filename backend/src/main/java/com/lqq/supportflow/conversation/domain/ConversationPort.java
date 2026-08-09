package com.lqq.supportflow.conversation.domain;
public interface ConversationPort { Conversation create(Long tenantId,Long customerId); boolean belongsTo(Long tenantId,Long customerId,Long conversationId); Generation submit(Long tenantId,Long conversationId,String content,String idempotencyKey); }
