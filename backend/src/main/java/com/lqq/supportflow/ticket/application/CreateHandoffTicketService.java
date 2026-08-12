package com.lqq.supportflow.ticket.application;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.lqq.supportflow.conversation.HandoffRequiredEvent;
import com.lqq.supportflow.eventing.OutboxService;
import com.lqq.supportflow.ticket.SlaDeadline;
import com.lqq.supportflow.ticket.domain.SlaMonitorPort;
import com.lqq.supportflow.ticket.domain.Ticket;
import com.lqq.supportflow.ticket.domain.TicketPort;
import com.lqq.supportflow.ticket.domain.TicketPriority;
import java.util.Map;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class CreateHandoffTicketService {
    private final TicketPort tickets;
    private final SlaMonitorPort sla;
    private final OutboxService outbox;
    private final ObjectMapper json;

    public CreateHandoffTicketService(TicketPort tickets, SlaMonitorPort sla, OutboxService outbox, ObjectMapper json) {
        this.tickets = tickets;
        this.sla = sla;
        this.outbox = outbox;
        this.json = json;
    }

    @EventListener
    @Transactional
    public void on(HandoffRequiredEvent event) {
        Ticket ticket = tickets.create(event.tenantId(), event.customerId(), event.conversationId(), event.reason(), TicketPriority.NORMAL);
        schedule(new SlaDeadline(event.tenantId(), ticket.id(), "FIRST_RESPONSE", ticket.firstResponseDueAt()));
        schedule(new SlaDeadline(event.tenantId(), ticket.id(), "RESOLUTION", ticket.resolutionDueAt()));
    }

    private void schedule(SlaDeadline deadline) {
        if (!sla.markAlerted(deadline)) return;
        try {
            String payload = json.writeValueAsString(Map.of(
                    "tenantId", deadline.tenantId().toString(),
                    "ticketId", deadline.ticketId().toString(),
                    "type", deadline.type(),
                    "dueAt", deadline.dueAt().toString()));
            outbox.record(deadline.tenantId(), "ticket.sla." + deadline.type().toLowerCase(),
                    "ticket", deadline.ticketId().toString(), payload);
        } catch (JsonProcessingException exception) {
            throw new IllegalStateException("could not serialize SLA schedule", exception);
        }
    }
}
