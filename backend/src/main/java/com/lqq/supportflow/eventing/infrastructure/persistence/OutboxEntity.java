package com.lqq.supportflow.eventing.infrastructure.persistence;
import com.baomidou.mybatisplus.annotation.*; import java.time.Instant;
@TableName("event_outbox") public class OutboxEntity { @TableId(type=IdType.ASSIGN_ID) public Long id; public Long tenantId; public String eventType; public String aggregateType; public String aggregateId; public String payload; public String status; public Integer attemptCount; public Instant createdAt; public Instant publishedAt; }
