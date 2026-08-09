package com.lqq.supportflow.eventing.domain;
import java.time.Instant;
public record OutboxEvent(Long id,Long tenantId,String eventType,String aggregateType,String aggregateId,String payload,int attemptCount,Instant createdAt) { }
