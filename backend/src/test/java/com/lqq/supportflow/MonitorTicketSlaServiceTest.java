package com.lqq.supportflow;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.argThat;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.lqq.supportflow.eventing.OutboxService;
import com.lqq.supportflow.shared.ActiveTenantProvider;
import com.lqq.supportflow.shared.TenantContext;
import com.lqq.supportflow.ticket.SlaDeadline;
import com.lqq.supportflow.ticket.application.MonitorTicketSlaService;
import com.lqq.supportflow.ticket.domain.SlaMonitorPort;
import java.time.Instant;
import java.util.List;
import org.junit.jupiter.api.Test;

class MonitorTicketSlaServiceTest {
    @Test
    void emitsOneOutboxEventOnlyAfterRecordingAnAlert() {
        SlaMonitorPort monitor = mock(SlaMonitorPort.class);
        OutboxService outbox = mock(OutboxService.class);
        ActiveTenantProvider tenants = mock(ActiveTenantProvider.class);
        SlaDeadline deadline = new SlaDeadline(7L, 9L, "FIRST_RESPONSE", Instant.parse("2026-08-09T00:00:00Z"));
        when(tenants.findActiveTenantIds()).thenReturn(List.of(7L));
        when(monitor.dueAt(any())).thenReturn(List.of(deadline));
        when(monitor.markAlerted(deadline)).thenReturn(true);

        new MonitorTicketSlaService(monitor, outbox, new ObjectMapper(), tenants).monitor();

        verify(outbox).record(eq(7L), eq("ticket.sla.first_response"), eq("ticket"), eq("9"), argThat(payload ->
                payload.contains("\"tenantId\":\"7\"") && payload.contains("\"ticketId\":\"9\"")
                        && payload.contains("\"type\":\"FIRST_RESPONSE\"")
                        && payload.contains("\"dueAt\":\"2026-08-09T00:00:00Z\"")));
        org.assertj.core.api.Assertions.assertThat(TenantContext.current()).isEmpty();
    }
}
