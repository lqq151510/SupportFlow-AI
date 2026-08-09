package com.lqq.supportflow.eventing.domain;
import java.util.List;
public interface OutboxPort { void record(Long tenantId,String eventType,String aggregateType,String aggregateId,String payload); List<OutboxEvent> pending(int limit); void markPublished(Long eventId); }
