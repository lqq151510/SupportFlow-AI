package com.lqq.supportflow;

import static org.mockito.ArgumentMatchers.argThat;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.lqq.supportflow.conversation.HandoffRequiredEvent;
import com.lqq.supportflow.eventing.OutboxService;
import com.lqq.supportflow.ticket.application.CreateHandoffTicketService;
import com.lqq.supportflow.ticket.domain.SlaMonitorPort;
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
        SlaMonitorPort sla = mock(SlaMonitorPort.class);
        OutboxService outbox = mock(OutboxService.class);
        Instant first = Instant.now().plusSeconds(600);
        Instant resolution = first.plusSeconds(3600);
        Ticket ticket = new Ticket(11L, 9L, "handoff", TicketStatus.NEW, TicketPriority.NORMAL, null, first, resolution);
        when(tickets.create(7L, 9L, 10L, "handoff", TicketPriority.NORMAL)).thenReturn(ticket);
        when(sla.markAlerted(org.mockito.ArgumentMatchers.any())).thenReturn(true);

        new CreateHandoffTicketService(tickets, sla, outbox, new ObjectMapper())
                .on(new HandoffRequiredEvent(7L, 9L, 10L, 12L, "handoff"));

        verify(outbox).record(eq(7L), eq("ticket.sla.first_response"), eq("ticket"), eq("11"),
                argThat(payload -> payload.contains(first.toString()) && payload.contains("\"ticketId\":\"11\"")));
        verify(outbox).record(eq(7L), eq("ticket.sla.resolution"), eq("ticket"), eq("11"),
                argThat(payload -> payload.contains(resolution.toString())));
    }
}
