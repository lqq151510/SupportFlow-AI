package com.lqq.supportflow.eventing.infrastructure.messaging;

import com.lqq.supportflow.eventing.PublishedOutboxEvent;
import com.lqq.supportflow.eventing.domain.OutboxDeliveryGateway;
import com.lqq.supportflow.eventing.domain.OutboxEvent;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.stereotype.Component;

@Component
@ConditionalOnProperty(prefix = "supportflow.eventing.rocketmq", name = "enabled", havingValue = "false", matchIfMissing = true)
public class LocalOutboxDeliveryGateway implements OutboxDeliveryGateway {
    private final ApplicationEventPublisher publisher;
    public LocalOutboxDeliveryGateway(ApplicationEventPublisher publisher) { this.publisher = publisher; }
    @Override public void publish(OutboxEvent event) { publisher.publishEvent(new PublishedOutboxEvent(event.id(), event.tenantId(), event.eventType(), event.payload())); }
}
