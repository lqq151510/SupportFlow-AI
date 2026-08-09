package com.lqq.supportflow.commerce.domain;

import java.util.List;
import java.util.Optional;

public interface CustomerOrderPort {

    void createDemoOrder(Long tenantId, Long customerId);

    List<CustomerOrder> findByCustomer(Long tenantId, Long customerId);

    Optional<CustomerOrder> findByOrderNo(Long tenantId, Long customerId, String orderNo);
}
