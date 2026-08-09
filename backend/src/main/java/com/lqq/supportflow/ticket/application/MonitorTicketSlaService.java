package com.lqq.supportflow.ticket.application;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.lqq.supportflow.eventing.OutboxService;
import com.lqq.supportflow.ticket.SlaDeadline;
import com.lqq.supportflow.ticket.domain.SlaMonitorPort;
import java.time.Instant;
import java.util.Map;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

@Service
public class MonitorTicketSlaService {
    private final SlaMonitorPort monitor;
    private final OutboxService outbox;
    private final ObjectMapper json;

    public MonitorTicketSlaService(SlaMonitorPort monitor, OutboxService outbox, ObjectMapper json) {
        this.monitor = monitor;
        this.outbox = outbox;
        this.json = json;
    }

    @Scheduled(initialDelayString = "${supportflow.ticket.sla.initial-delay:PT1M}", fixedDelayString = "${supportflow.ticket.sla.fixed-delay:PT1M}")
    public void monitor() {
        for (SlaDeadline deadline : monitor.dueAt(Instant.now())) {
            if (monitor.markAlerted(deadline)) {
                outbox.record(deadline.tenantId(), "ticket.sla." + deadline.type().toLowerCase(), "ticket", deadline.ticketId().toString(), payload(deadline));
            }
        }
    }

    private String payload(SlaDeadline deadline) {
        try {
            return json.writeValueAsString(Map.of(
                    "tenantId", deadline.tenantId(),
                    "ticketId", deadline.ticketId(),
                    "type", deadline.type(),
                    "dueAt", deadline.dueAt().toString()));
        } catch (JsonProcessingException exception) {
            throw new IllegalStateException("could not serialize SLA alert", exception);
        }
    }
}
