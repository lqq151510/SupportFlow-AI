package com.lqq.supportflow.ticket.application;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.lqq.supportflow.eventing.OutboxService;
import com.lqq.supportflow.ticket.SlaDeadline;
import com.lqq.supportflow.ticket.domain.SlaMonitorPort;
import java.util.Locale;
import java.util.Map;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ScheduleTicketSlaAlertService {
    private final SlaMonitorPort monitor;
    private final OutboxService outbox;
    private final ObjectMapper json;

    public ScheduleTicketSlaAlertService(SlaMonitorPort monitor, OutboxService outbox, ObjectMapper json) {
        this.monitor = monitor;
        this.outbox = outbox;
        this.json = json;
    }

    @Transactional
    public boolean schedule(SlaDeadline deadline) {
        if (!monitor.markAlerted(deadline)) return false;
        outbox.record(deadline.tenantId(), "ticket.sla." + deadline.type().toLowerCase(Locale.ROOT),
                "ticket", deadline.ticketId().toString(), payload(deadline));
        return true;
    }

    private String payload(SlaDeadline deadline) {
        try {
            return json.writeValueAsString(Map.of(
                    "tenantId", deadline.tenantId().toString(),
                    "ticketId", deadline.ticketId().toString(),
                    "type", deadline.type(),
                    "dueAt", deadline.dueAt().toString()));
        } catch (JsonProcessingException exception) {
            throw new IllegalStateException("could not serialize SLA alert", exception);
        }
    }
}
