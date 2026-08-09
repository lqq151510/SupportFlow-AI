package com.lqq.supportflow.commerce.application;

import com.lqq.supportflow.commerce.domain.CustomerOrder;
import com.lqq.supportflow.commerce.domain.CustomerOrderPort;
import java.util.List;
import java.util.Optional;
import org.springframework.stereotype.Service;

@Service
public class QueryCustomerOrders {

    private final CustomerOrderPort orders;

    public QueryCustomerOrders(CustomerOrderPort orders) {
        this.orders = orders;
    }

    public List<CustomerOrder> list(Long tenantId, Long customerId) {
        return orders.findByCustomer(tenantId, customerId);
    }

    public Optional<CustomerOrder> find(Long tenantId, Long customerId, String orderNo) {
        return orders.findByOrderNo(tenantId, customerId, orderNo);
    }
}
