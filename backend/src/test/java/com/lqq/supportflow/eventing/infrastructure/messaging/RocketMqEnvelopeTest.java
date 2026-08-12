package com.lqq.supportflow.eventing.infrastructure.messaging;

import static org.assertj.core.api.Assertions.assertThat;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.lqq.supportflow.eventing.PublishedOutboxEvent;
import com.lqq.supportflow.shared.TenantContext;
import java.time.Instant;
import java.util.concurrent.atomic.AtomicReference;
import com.lqq.supportflow.eventing.domain.OutboxEvent;
import org.apache.rocketmq.common.message.Message;
import org.junit.jupiter.api.Test;

class RocketMqEnvelopeTest {
    @Test
    void acceptsVersionOneWithStringIdsAndRestoresTenantContext() throws Exception {
        ObjectMapper json = new ObjectMapper().findAndRegisterModules();
        AtomicReference<PublishedOutboxEvent> published = new AtomicReference<>();
        AtomicReference<Long> tenantDuringPublish = new AtomicReference<>();
        RocketMqSpringEventConsumer consumer = new RocketMqSpringEventConsumer(json, event -> {
            published.set((PublishedOutboxEvent) event);
            tenantDuringPublish.set(TenantContext.current().orElseThrow().tenantId());
        }, "unused:9876", "unused", "unused", 1);
        byte[] body = json.writeValueAsBytes(new RocketMqOutboxDeliveryGateway.RocketMqEnvelope(
                1, "41", "73", "approval.approved", "{\"schemaVersion\":1}", Instant.now()));

        assertThat(consumer.handle(body)).isTrue();
        assertThat(published.get()).isEqualTo(new PublishedOutboxEvent(
                41L, 73L, "approval.approved", "{\"schemaVersion\":1}"));
        assertThat(tenantDuringPublish.get()).isEqualTo(73L);
        assertThat(TenantContext.current()).isEmpty();
    }

    @Test
    void rejectsUnknownVersionsAndMalformedIds() throws Exception {
        ObjectMapper json = new ObjectMapper().findAndRegisterModules();
        RocketMqSpringEventConsumer consumer = new RocketMqSpringEventConsumer(
                json, event -> { throw new AssertionError("must not publish"); },
                "unused:9876", "unused", "unused", 1);
        byte[] unknown = json.writeValueAsBytes(new RocketMqOutboxDeliveryGateway.RocketMqEnvelope(
                2, "41", "73", "approval.approved", "{}", Instant.now()));
        byte[] malformed = json.writeValueAsBytes(new RocketMqOutboxDeliveryGateway.RocketMqEnvelope(
                1, "not-a-number", "73", "approval.approved", "{}", Instant.now()));

        assertThat(consumer.handle(unknown)).isFalse();
        assertThat(consumer.handle(malformed)).isFalse();
        assertThat(TenantContext.current()).isEmpty();
    }

    @Test
    void assignsBrokerDeliveryTimeToFutureSlaEventsOnly() {
        ObjectMapper json = new ObjectMapper().findAndRegisterModules();
        RocketMqOutboxDeliveryGateway gateway = new RocketMqOutboxDeliveryGateway(json, "unused:9876", "events");
        Instant dueAt = Instant.now().plusSeconds(300);
        OutboxEvent event = new OutboxEvent(1L, 7L, "ticket.sla.first_response", "ticket", "11",
                "{\"ticketId\":\"11\",\"dueAt\":\"" + dueAt + "\"}", 0, Instant.now());
        Message message = new Message("events", new byte[0]);

        gateway.applyDeliveryTime(message, event);

        assertThat(message.getDeliverTimeMs()).isEqualTo(dueAt.toEpochMilli());
    }
}
