package com.lqq.supportflow.eventing.domain;
import com.lqq.supportflow.eventing.FailedOutboxEvent;
import java.util.List;
public interface OutboxPort { void record(Long tenantId,String eventType,String aggregateType,String aggregateId,String payload); List<OutboxEvent> pending(int limit); List<FailedOutboxEvent> failed(Long tenantId, int limit); void markPublished(Long eventId); void recordFailure(Long eventId, String reason); }
