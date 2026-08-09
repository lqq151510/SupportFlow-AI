package com.lqq.supportflow.commerce.domain;
import java.util.Optional;
public interface ShipmentPort { void createDemo(Long tenantId,Long customerId); Optional<Shipment> find(Long tenantId,Long customerId,String orderNo); }
