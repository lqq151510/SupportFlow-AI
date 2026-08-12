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
    private final ObjectMapper json; private final ApplicationEventPublisher publisher; private final String nameserver; private final String topic; private final String consumerGroup; private final int maxReconsumeTimes; private DefaultMQPushConsumer consumer;
    public RocketMqSpringEventConsumer(ObjectMapper json, ApplicationEventPublisher publisher, @Value("${supportflow.eventing.rocketmq.nameserver}") String nameserver, @Value("${supportflow.eventing.rocketmq.topic}") String topic, @Value("${supportflow.eventing.rocketmq.consumer-group:supportflow-event-consumer}") String consumerGroup, @Value("${supportflow.eventing.rocketmq.max-reconsume-times:8}") int maxReconsumeTimes) { this.json = json; this.publisher = publisher; this.nameserver = nameserver; this.topic = topic; this.consumerGroup = consumerGroup; this.maxReconsumeTimes = maxReconsumeTimes; }
    @PostConstruct void start() { try { consumer = new DefaultMQPushConsumer(consumerGroup); consumer.setNamesrvAddr(nameserver); consumer.setConsumeFromWhere(ConsumeFromWhere.CONSUME_FROM_LAST_OFFSET); consumer.setMaxReconsumeTimes(maxReconsumeTimes); consumer.subscribe(topic, "*"); consumer.registerMessageListener((org.apache.rocketmq.client.consumer.listener.MessageListenerConcurrently) (messages, context) -> { for (var message : messages) { if (!handle(message.getBody())) return ConsumeConcurrentlyStatus.RECONSUME_LATER; } return ConsumeConcurrentlyStatus.CONSUME_SUCCESS; }); consumer.start(); } catch (Exception exception) { throw new IllegalStateException("RocketMQ consumer failed to start", exception); } }
    boolean handle(byte[] body) { try { RocketMqOutboxDeliveryGateway.RocketMqEnvelope envelope = json.readValue(body, RocketMqOutboxDeliveryGateway.RocketMqEnvelope.class); if(envelope.schemaVersion()!=1)return false;Long tenantId=Long.valueOf(envelope.tenantId());Long eventId=Long.valueOf(envelope.eventId());if(tenantId<=0||eventId<=0||envelope.eventType()==null||envelope.eventType().isBlank())return false;TenantContext.set(new AuthenticatedPrincipal(0L, tenantId, 0L, "SYSTEM")); try { publisher.publishEvent(new PublishedOutboxEvent(eventId, tenantId, envelope.eventType(), envelope.payload())); return true; } finally { TenantContext.clear(); } } catch (Exception exception) { TenantContext.clear(); return false; } }
    @PreDestroy void stop() { if (consumer != null) consumer.shutdown(); }
}
