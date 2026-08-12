package com.lqq.supportflow.ticket.application;

import com.lqq.supportflow.shared.ActiveTenantProvider;
import com.lqq.supportflow.shared.AuthenticatedPrincipal;
import com.lqq.supportflow.shared.TenantContext;
import com.lqq.supportflow.ticket.SlaDeadline;
import com.lqq.supportflow.ticket.domain.SlaMonitorPort;
import java.time.Instant;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

@Service
public class MonitorTicketSlaService {
    private final SlaMonitorPort monitor;
    private final ScheduleTicketSlaAlertService slaAlerts;
    private final ActiveTenantProvider tenants;

    public MonitorTicketSlaService(SlaMonitorPort monitor, ScheduleTicketSlaAlertService slaAlerts, ActiveTenantProvider tenants) {
        this.monitor = monitor;
        this.slaAlerts = slaAlerts;
        this.tenants = tenants;
    }

    @Scheduled(initialDelayString = "${supportflow.ticket.sla.initial-delay:PT1M}", fixedDelayString = "${supportflow.ticket.sla.fixed-delay:PT1M}")
    public void monitor() {
        for (Long tenantId : tenants.findActiveTenantIds()) {
            TenantContext.set(new AuthenticatedPrincipal(0L, tenantId, 0L, "SYSTEM"));
            try {
                for (SlaDeadline deadline : monitor.dueAt(Instant.now())) {
                    slaAlerts.schedule(deadline);
                }
            } finally {
                TenantContext.clear();
            }
        }
    }
}
