package com.lqq.supportflow;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import com.lqq.supportflow.commerce.application.CheckRefundEligibility;
import com.lqq.supportflow.commerce.domain.CustomerOrder;
import com.lqq.supportflow.commerce.domain.CustomerOrderPort;
import java.math.BigDecimal;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.Optional;
import org.junit.jupiter.api.Test;

class CheckRefundEligibilityTest {

    @Test
    void distinguishesEligibleOrdersFromUnpaidAndExpiredOrders() {
        CustomerOrderPort orders = mock(CustomerOrderPort.class);
        when(orders.findByOrderNo(7L, 8L, "PAID"))
                .thenReturn(Optional.of(order("PAID", Instant.now().minus(29, ChronoUnit.DAYS))));
        when(orders.findByOrderNo(7L, 8L, "UNPAID"))
                .thenReturn(Optional.of(order("CREATED", Instant.now())));
        when(orders.findByOrderNo(7L, 8L, "EXPIRED"))
                .thenReturn(Optional.of(order("PAID", Instant.now().minus(31, ChronoUnit.DAYS))));
        CheckRefundEligibility service = new CheckRefundEligibility(orders);

        assertThat(service.check(7L, 8L, "PAID").eligible()).isTrue();
        assertThat(service.check(7L, 8L, "UNPAID").reason()).isEqualTo("order is not paid");
        assertThat(service.check(7L, 8L, "EXPIRED").reason()).isEqualTo("refund window expired");
    }

    @Test
    void rejectsOrdersOutsideTheCustomerScope() {
        CustomerOrderPort orders = mock(CustomerOrderPort.class);
        when(orders.findByOrderNo(7L, 8L, "MISSING")).thenReturn(Optional.empty());

        assertThatThrownBy(() -> new CheckRefundEligibility(orders).check(7L, 8L, "MISSING"))
                .isInstanceOf(IllegalArgumentException.class);
    }

    private CustomerOrder order(String status, Instant createdAt) {
        return new CustomerOrder("DEMO-001", status, new BigDecimal("88.00"), "CNY", createdAt);
    }
}
