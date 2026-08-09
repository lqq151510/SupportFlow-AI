package com.lqq.supportflow.conversation.infrastructure.persistence;
import com.baomidou.mybatisplus.annotation.*; import java.time.Instant;
@TableName("generations") public class GenerationEntity { @TableId(type=IdType.ASSIGN_ID) public Long id; public Long tenantId; public Long conversationId; public Long userMessageId; public String status; public String errorCode; public Integer inputTokens; public Integer outputTokens; public Long latencyMs; public Instant createdAt; public Instant updatedAt; }
