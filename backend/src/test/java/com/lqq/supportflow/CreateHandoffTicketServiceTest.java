package com.lqq.supportflow;

import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.lqq.supportflow.conversation.HandoffRequiredEvent;
import com.lqq.supportflow.ticket.SlaDeadline;
import com.lqq.supportflow.ticket.application.CreateHandoffTicketService;
import com.lqq.supportflow.ticket.application.ScheduleTicketSlaAlertService;
import com.lqq.supportflow.ticket.domain.Ticket;
import com.lqq.supportflow.ticket.domain.TicketPort;
import com.lqq.supportflow.ticket.domain.TicketPriority;
import com.lqq.supportflow.ticket.domain.TicketStatus;
import java.time.Instant;
import org.junit.jupiter.api.Test;

class CreateHandoffTicketServiceTest {
    @Test
    void schedulesBothSlaDeadlinesInTheSameHandoffFlow() {
        TicketPort tickets = mock(TicketPort.class);
        ScheduleTicketSlaAlertService slaAlerts = mock(ScheduleTicketSlaAlertService.class);
        Instant first = Instant.now().plusSeconds(600);
        Instant resolution = first.plusSeconds(3600);
        Ticket ticket = new Ticket(11L, 9L, 10L, "handoff", TicketStatus.NEW, TicketPriority.NORMAL, null, first, resolution);
        when(tickets.create(7L, 9L, 10L, "handoff", TicketPriority.NORMAL)).thenReturn(ticket);

        new CreateHandoffTicketService(tickets, slaAlerts)
                .on(new HandoffRequiredEvent(7L, 9L, 10L, 12L, "handoff"));

        verify(slaAlerts).schedule(new SlaDeadline(7L, 11L, "FIRST_RESPONSE", first));
        verify(slaAlerts).schedule(new SlaDeadline(7L, 11L, "RESOLUTION", resolution));
    }
}
