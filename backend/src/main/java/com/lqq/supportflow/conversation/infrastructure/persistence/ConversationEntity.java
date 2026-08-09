package com.lqq.supportflow.conversation.infrastructure.persistence;
import com.baomidou.mybatisplus.annotation.*; import java.time.Instant;
@TableName("conversations") public class ConversationEntity { @TableId(type=IdType.ASSIGN_ID) public Long id; public Long tenantId; public Long customerId; public String status; public Instant createdAt; public Instant updatedAt; }
