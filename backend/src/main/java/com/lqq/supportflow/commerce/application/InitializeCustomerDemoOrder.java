package com.lqq.supportflow.commerce.application;

import com.lqq.supportflow.commerce.domain.CustomerOrderPort;
import com.lqq.supportflow.identity.CustomerRegisteredEvent;
import com.lqq.supportflow.shared.AuthenticatedPrincipal;
import com.lqq.supportflow.shared.TenantContext;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

@Component
public class InitializeCustomerDemoOrder {

    private final CustomerOrderPort orders;

    public InitializeCustomerDemoOrder(CustomerOrderPort orders) {
        this.orders = orders;
    }

    @EventListener
    @Transactional
    public void on(CustomerRegisteredEvent event) {
        TenantContext.set(new AuthenticatedPrincipal(event.customerId(), event.tenantId(), 0L, "CUSTOMER"));
        try {
            orders.createDemoOrder(event.tenantId(), event.customerId());
        } finally {
            TenantContext.clear();
        }
    }
}
