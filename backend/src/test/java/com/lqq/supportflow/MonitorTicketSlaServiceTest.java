package com.lqq.supportflow;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.lqq.supportflow.shared.ActiveTenantProvider;
import com.lqq.supportflow.shared.TenantContext;
import com.lqq.supportflow.ticket.SlaDeadline;
import com.lqq.supportflow.ticket.application.MonitorTicketSlaService;
import com.lqq.supportflow.ticket.application.ScheduleTicketSlaAlertService;
import com.lqq.supportflow.ticket.domain.SlaMonitorPort;
import java.time.Instant;
import java.util.List;
import org.junit.jupiter.api.Test;

class MonitorTicketSlaServiceTest {
    @Test
    void emitsOneOutboxEventOnlyAfterRecordingAnAlert() {
        SlaMonitorPort monitor = mock(SlaMonitorPort.class);
        ScheduleTicketSlaAlertService slaAlerts = mock(ScheduleTicketSlaAlertService.class);
        ActiveTenantProvider tenants = mock(ActiveTenantProvider.class);
        SlaDeadline deadline = new SlaDeadline(7L, 9L, "FIRST_RESPONSE", Instant.parse("2026-08-09T00:00:00Z"));
        when(tenants.findActiveTenantIds()).thenReturn(List.of(7L));
        when(monitor.dueAt(any())).thenReturn(List.of(deadline));

        new MonitorTicketSlaService(monitor, slaAlerts, tenants).monitor();

        verify(slaAlerts).schedule(deadline);
        org.assertj.core.api.Assertions.assertThat(TenantContext.current()).isEmpty();
    }
}
