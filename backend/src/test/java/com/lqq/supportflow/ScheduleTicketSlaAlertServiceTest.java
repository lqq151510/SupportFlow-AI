package com.lqq.supportflow;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.argThat;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.lqq.supportflow.eventing.OutboxService;
import com.lqq.supportflow.ticket.SlaDeadline;
import com.lqq.supportflow.ticket.application.ScheduleTicketSlaAlertService;
import com.lqq.supportflow.ticket.domain.SlaMonitorPort;
import java.time.Instant;
import org.junit.jupiter.api.Test;

class ScheduleTicketSlaAlertServiceTest {
    @Test
    void recordsTheSlaMarkerAndOutboxPayloadTogether() {
        SlaMonitorPort monitor = mock(SlaMonitorPort.class);
        OutboxService outbox = mock(OutboxService.class);
        SlaDeadline deadline = new SlaDeadline(7L, 9L, "FIRST_RESPONSE",
                Instant.parse("2026-08-09T00:00:00Z"));
        when(monitor.markAlerted(deadline)).thenReturn(true);

        boolean scheduled = new ScheduleTicketSlaAlertService(monitor, outbox, new ObjectMapper())
                .schedule(deadline);

        assertThat(scheduled).isTrue();
        verify(outbox).record(eq(7L), eq("ticket.sla.first_response"), eq("ticket"), eq("9"), argThat(payload ->
                payload.contains("\"tenantId\":\"7\"") && payload.contains("\"ticketId\":\"9\"")
                        && payload.contains("\"type\":\"FIRST_RESPONSE\"")
                        && payload.contains("\"dueAt\":\"2026-08-09T00:00:00Z\"")));
    }

    @Test
    void skipsTheOutboxWhenTheDeadlineWasAlreadyScheduled() {
        SlaMonitorPort monitor = mock(SlaMonitorPort.class);
        OutboxService outbox = mock(OutboxService.class);
        SlaDeadline deadline = new SlaDeadline(7L, 9L, "RESOLUTION", Instant.now());
        when(monitor.markAlerted(deadline)).thenReturn(false);

        boolean scheduled = new ScheduleTicketSlaAlertService(monitor, outbox, new ObjectMapper())
                .schedule(deadline);

        assertThat(scheduled).isFalse();
        verify(outbox, never()).record(eq(7L), eq("ticket.sla.resolution"), eq("ticket"), eq("9"),
                org.mockito.ArgumentMatchers.anyString());
    }
}
