package com.lqq.supportflow.eventing.infrastructure.messaging;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.lqq.supportflow.eventing.PublishedOutboxEvent;
import com.lqq.supportflow.shared.AuthenticatedPrincipal;
import com.lqq.supportflow.shared.TenantContext;
import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import org.apache.rocketmq.client.consumer.DefaultMQPushConsumer;
import org.apache.rocketmq.client.consumer.listener.ConsumeConcurrentlyStatus;
import org.apache.rocketmq.common.consumer.ConsumeFromWhere;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.stereotype.Component;

@Component
@ConditionalOnProperty(prefix = "supportflow.eventing.rocketmq", name = "enabled", havingValue = "true")
public class RocketMqSpringEventConsumer {
    private final ObjectMapper json; private final ApplicationEventPublisher publisher; private final String nameserver; private final String topic; private DefaultMQPushConsumer consumer;
    public RocketMqSpringEventConsumer(ObjectMapper json, ApplicationEventPublisher publisher, @Value("${supportflow.eventing.rocketmq.nameserver}") String nameserver, @Value("${supportflow.eventing.rocketmq.topic}") String topic) { this.json = json; this.publisher = publisher; this.nameserver = nameserver; this.topic = topic; }
    @PostConstruct void start() { try { consumer = new DefaultMQPushConsumer("supportflow-event-consumer"); consumer.setNamesrvAddr(nameserver); consumer.setConsumeFromWhere(ConsumeFromWhere.CONSUME_FROM_LAST_OFFSET); consumer.subscribe(topic, "*"); consumer.registerMessageListener((org.apache.rocketmq.client.consumer.listener.MessageListenerConcurrently) (messages, context) -> { for (var message : messages) handle(message.getBody()); return ConsumeConcurrentlyStatus.CONSUME_SUCCESS; }); consumer.start(); } catch (Exception exception) { throw new IllegalStateException("RocketMQ consumer failed to start", exception); } }
    private void handle(byte[] body) { try { RocketMqOutboxDeliveryGateway.RocketMqEnvelope envelope = json.readValue(body, RocketMqOutboxDeliveryGateway.RocketMqEnvelope.class); TenantContext.set(new AuthenticatedPrincipal(0L, envelope.tenantId(), 0L, "SYSTEM")); try { publisher.publishEvent(new PublishedOutboxEvent(envelope.eventId(), envelope.tenantId(), envelope.eventType(), envelope.payload())); } finally { TenantContext.clear(); } } catch (Exception exception) { throw new IllegalStateException("RocketMQ event handling failed", exception); } }
    @PreDestroy void stop() { if (consumer != null) consumer.shutdown(); }
}
