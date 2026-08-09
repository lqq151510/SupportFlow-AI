package com.lqq.supportflow.eventing.application;

import com.lqq.supportflow.identity.domain.IdentityRegistrationPort;
import com.lqq.supportflow.shared.AuthenticatedPrincipal;
import com.lqq.supportflow.shared.TenantContext;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Component
public class OutboxDispatchScheduler {
    private final DispatchOutboxService dispatch;
    private final IdentityRegistrationPort tenants;

    public OutboxDispatchScheduler(DispatchOutboxService dispatch, IdentityRegistrationPort tenants) {
        this.dispatch = dispatch;
        this.tenants = tenants;
    }

    @Scheduled(initialDelayString = "${supportflow.eventing.dispatch.initial-delay:PT30S}", fixedDelayString = "${supportflow.eventing.dispatch.fixed-delay:PT30S}")
    public void dispatchPendingEvents() {
        for (Long tenantId : tenants.findActiveTenantIds()) {
            TenantContext.set(new AuthenticatedPrincipal(0L, tenantId, 0L, "SYSTEM"));
            try {
                dispatch.dispatch(100);
            } finally {
                TenantContext.clear();
            }
        }
    }
}
