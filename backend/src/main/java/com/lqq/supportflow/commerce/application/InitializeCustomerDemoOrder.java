package com.lqq.supportflow.commerce.application;

import com.lqq.supportflow.commerce.domain.CustomerOrderPort;
import com.lqq.supportflow.identity.CustomerRegisteredEvent;
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
        orders.createDemoOrder(event.tenantId(), event.customerId());
    }
}
