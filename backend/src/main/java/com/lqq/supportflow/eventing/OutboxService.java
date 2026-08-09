package com.lqq.supportflow.eventing;
import com.lqq.supportflow.eventing.domain.OutboxPort; import org.springframework.stereotype.Service;
@Service public class OutboxService { private final OutboxPort outbox; public OutboxService(OutboxPort outbox){this.outbox=outbox;} public void record(Long tenantId,String eventType,String aggregateType,String aggregateId,String payload){outbox.record(tenantId,eventType,aggregateType,aggregateId,payload);} public java.util.List<FailedOutboxEvent> failed(Long tenantId,int limit){return outbox.failed(tenantId,limit);}}
