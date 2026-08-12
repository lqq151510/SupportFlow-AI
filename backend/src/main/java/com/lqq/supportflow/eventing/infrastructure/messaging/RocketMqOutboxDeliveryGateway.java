package com.lqq.supportflow.eventing.infrastructure.messaging;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.lqq.supportflow.eventing.domain.OutboxDeliveryGateway;
import com.lqq.supportflow.eventing.domain.OutboxEvent;
import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import org.apache.rocketmq.client.producer.DefaultMQProducer;
import org.apache.rocketmq.common.message.Message;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

@Component
@ConditionalOnProperty(prefix = "supportflow.eventing.rocketmq", name = "enabled", havingValue = "true")
public class RocketMqOutboxDeliveryGateway implements OutboxDeliveryGateway {
    private final ObjectMapper json; private final String nameserver; private final String topic; private DefaultMQProducer producer;
    public RocketMqOutboxDeliveryGateway(ObjectMapper json, @Value("${supportflow.eventing.rocketmq.nameserver}") String nameserver, @Value("${supportflow.eventing.rocketmq.topic}") String topic) { this.json = json; this.nameserver = nameserver; this.topic = topic; }
    @PostConstruct void start() { try { producer = new DefaultMQProducer("supportflow-outbox-producer"); producer.setNamesrvAddr(nameserver); producer.start(); } catch (Exception exception) { throw new IllegalStateException("RocketMQ producer failed to start", exception); } }
    @Override public void publish(OutboxEvent event) { try { Message message = new Message(topic, event.eventType().replace('.', '_'), event.tenantId() + ":" + event.id(), json.writeValueAsBytes(new RocketMqEnvelope(1, event.id().toString(), event.tenantId().toString(), event.eventType(), event.payload(), event.createdAt()))); message.putUserProperty("schemaVersion", "1"); producer.send(message); } catch (Exception exception) { throw new IllegalStateException("RocketMQ publish failed", exception); } }
    @PreDestroy void stop() { if (producer != null) producer.shutdown(); }
    public record RocketMqEnvelope(int schemaVersion, String eventId, String tenantId,
                                   String eventType, String payload, java.time.Instant occurredAt) { }
}
