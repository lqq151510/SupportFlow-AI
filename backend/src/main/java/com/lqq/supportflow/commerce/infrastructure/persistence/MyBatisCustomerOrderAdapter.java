package com.lqq.supportflow.commerce.infrastructure.persistence;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.lqq.supportflow.commerce.domain.CustomerOrder;
import com.lqq.supportflow.commerce.domain.CustomerOrderPort;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;
import java.util.Optional;
import org.springframework.stereotype.Component;

@Component
public class MyBatisCustomerOrderAdapter implements CustomerOrderPort {

    private static final String DEMO_ORDER_NO = "DEMO-001";

    private final OrderMapper orders;

    public MyBatisCustomerOrderAdapter(OrderMapper orders) {
        this.orders = orders;
    }

    @Override
    public void createDemoOrder(Long tenantId, Long customerId) {
        Instant now = Instant.now();
        OrderEntity order = new OrderEntity();
        order.tenantId = tenantId;
        order.customerId = customerId;
        order.orderNo = DEMO_ORDER_NO;
        order.status = "PAID";
        order.totalAmount = new BigDecimal("99.00");
        order.currency = "CNY";
        order.createdAt = now;
        order.updatedAt = now;
        orders.insert(order);
    }

    @Override
    public List<CustomerOrder> findByCustomer(Long tenantId, Long customerId) {
        return orders.selectList(new QueryWrapper<OrderEntity>()
                        .eq("tenant_id", tenantId)
                        .eq("customer_id", customerId)
                        .orderByDesc("created_at"))
                .stream()
                .map(this::toDomain)
                .toList();
    }

    @Override
    public Optional<CustomerOrder> findByOrderNo(Long tenantId, Long customerId, String orderNo) {
        return Optional.ofNullable(orders.selectOne(new QueryWrapper<OrderEntity>()
                        .eq("tenant_id", tenantId)
                        .eq("customer_id", customerId)
                        .eq("order_no", orderNo)))
                .map(this::toDomain);
    }

    private CustomerOrder toDomain(OrderEntity order) {
        return new CustomerOrder(order.orderNo, order.status, order.totalAmount, order.currency, order.createdAt);
    }
}
