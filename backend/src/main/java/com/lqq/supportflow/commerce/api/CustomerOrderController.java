package com.lqq.supportflow.commerce.api;

import com.lqq.supportflow.commerce.application.QueryCustomerOrders;
import com.lqq.supportflow.commerce.domain.CustomerOrder;
import com.lqq.supportflow.shared.AuthenticatedPrincipal;
import java.util.List;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/customer/orders")
public class CustomerOrderController {

    private final QueryCustomerOrders orders;

    public CustomerOrderController(QueryCustomerOrders orders) {
        this.orders = orders;
    }

    @GetMapping
    List<CustomerOrder> list(@AuthenticationPrincipal AuthenticatedPrincipal principal) {
        return orders.list(principal.tenantId(), principal.userId());
    }

    @GetMapping("/{orderNo}")
    CustomerOrder find(@AuthenticationPrincipal AuthenticatedPrincipal principal, @PathVariable String orderNo) {
        return orders.find(principal.tenantId(), principal.userId(), orderNo)
                .orElseThrow(OrderNotFoundException::new);
    }

    @ResponseStatus(HttpStatus.NOT_FOUND)
    static class OrderNotFoundException extends RuntimeException { }
}
