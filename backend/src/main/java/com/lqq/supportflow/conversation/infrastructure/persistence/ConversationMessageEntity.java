package com.lqq.supportflow.conversation.infrastructure.persistence;
import com.baomidou.mybatisplus.annotation.*; import java.time.Instant;
@TableName("conversation_messages") public class ConversationMessageEntity { @TableId(type=IdType.ASSIGN_ID) public Long id; public Long tenantId; public Long conversationId; public String senderType; public String content; public String idempotencyKey; public Long generationId; public Instant createdAt; }
