package com.lqq.supportflow.eventing;
import com.lqq.supportflow.eventing.domain.ConsumerLedger; import org.springframework.stereotype.Service;
@Service public class EventConsumerService { private final ConsumerLedger ledger; public EventConsumerService(ConsumerLedger ledger){this.ledger=ledger;} public boolean claim(Long tenantId,String consumerName,Long eventId){return ledger.claim(tenantId,consumerName,eventId);}}
