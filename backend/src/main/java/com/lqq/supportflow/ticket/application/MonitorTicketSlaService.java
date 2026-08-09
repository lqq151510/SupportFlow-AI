package com.lqq.supportflow.ticket.application;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.lqq.supportflow.eventing.OutboxService;
import com.lqq.supportflow.identity.domain.IdentityRegistrationPort;
import com.lqq.supportflow.shared.AuthenticatedPrincipal;
import com.lqq.supportflow.shared.TenantContext;
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
    private final IdentityRegistrationPort tenants;

    public MonitorTicketSlaService(SlaMonitorPort monitor, OutboxService outbox, ObjectMapper json, IdentityRegistrationPort tenants) {
        this.monitor = monitor;
        this.outbox = outbox;
        this.json = json;
        this.tenants = tenants;
    }

    @Scheduled(initialDelayString = "${supportflow.ticket.sla.initial-delay:PT1M}", fixedDelayString = "${supportflow.ticket.sla.fixed-delay:PT1M}")
    public void monitor() {
        for (Long tenantId : tenants.findActiveTenantIds()) {
            TenantContext.set(new AuthenticatedPrincipal(0L, tenantId, 0L, "SYSTEM"));
            try {
                for (SlaDeadline deadline : monitor.dueAt(Instant.now())) {
                    if (monitor.markAlerted(deadline)) {
                        outbox.record(deadline.tenantId(), "ticket.sla." + deadline.type().toLowerCase(), "ticket", deadline.ticketId().toString(), payload(deadline));
                    }
                }
            } finally {
                TenantContext.clear();
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
