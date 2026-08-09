package com.lqq.supportflow.eventing.infrastructure.persistence;
import com.baomidou.mybatisplus.annotation.*; import java.time.Instant;
@TableName("consumed_events") public class ConsumedEventEntity { @TableId(type=IdType.ASSIGN_ID) public Long id; public Long tenantId; public String consumerName; public Long eventId; public Instant processedAt; }
