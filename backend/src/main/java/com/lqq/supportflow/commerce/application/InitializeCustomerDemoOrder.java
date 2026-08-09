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
    private final com.lqq.supportflow.commerce.domain.ShipmentPort shipments;

    public InitializeCustomerDemoOrder(CustomerOrderPort orders, com.lqq.supportflow.commerce.domain.ShipmentPort shipments) {
        this.orders = orders; this.shipments = shipments;
    }

    @EventListener
    @Transactional
    public void on(CustomerRegisteredEvent event) {
        TenantContext.set(new AuthenticatedPrincipal(event.customerId(), event.tenantId(), 0L, "CUSTOMER"));
        try {
            orders.createDemoOrder(event.tenantId(), event.customerId());
            shipments.createDemo(event.tenantId(), event.customerId());
        } finally {
            TenantContext.clear();
        }
    }
}
