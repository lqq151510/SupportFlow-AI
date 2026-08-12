package com.lqq.supportflow.commerce;

import com.lqq.supportflow.commerce.application.QueryCustomerOrders;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;
import org.springframework.stereotype.Service;

@Service
public class CustomerOrderCatalogService {
    private final QueryCustomerOrders orders;

    public CustomerOrderCatalogService(QueryCustomerOrders orders) { this.orders = orders; }

    public List<OrderView> list(Long tenantId, Long customerId) {
        return orders.list(tenantId, customerId).stream()
                .map(order -> new OrderView(order.orderNo(), order.status(), order.totalAmount(), order.currency(), order.createdAt()))
                .toList();
    }

    public record OrderView(String orderNo, String status, BigDecimal totalAmount, String currency, Instant createdAt) { }
}
