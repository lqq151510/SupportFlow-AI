package com.lqq.supportflow.ticket.application;

import com.lqq.supportflow.conversation.HandoffRequiredEvent;
import com.lqq.supportflow.ticket.SlaDeadline;
import com.lqq.supportflow.ticket.domain.Ticket;
import com.lqq.supportflow.ticket.domain.TicketPort;
import com.lqq.supportflow.ticket.domain.TicketPriority;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class CreateHandoffTicketService {
    private final TicketPort tickets;
    private final ScheduleTicketSlaAlertService slaAlerts;

    public CreateHandoffTicketService(TicketPort tickets, ScheduleTicketSlaAlertService slaAlerts) {
        this.tickets = tickets;
        this.slaAlerts = slaAlerts;
    }

    @EventListener
    @Transactional
    public void on(HandoffRequiredEvent event) {
        Ticket ticket = tickets.create(event.tenantId(), event.customerId(), event.conversationId(), event.reason(), TicketPriority.NORMAL);
        slaAlerts.schedule(new SlaDeadline(event.tenantId(), ticket.id(), "FIRST_RESPONSE", ticket.firstResponseDueAt()));
        slaAlerts.schedule(new SlaDeadline(event.tenantId(), ticket.id(), "RESOLUTION", ticket.resolutionDueAt()));
    }
}
