package com.lqq.supportflow.commerce;

import com.lqq.supportflow.commerce.application.CheckRefundEligibility;
import com.lqq.supportflow.commerce.application.QueryCustomerOrders;
import com.lqq.supportflow.commerce.application.QueryShipment;
import com.lqq.supportflow.commerce.domain.CustomerOrder;
import com.lqq.supportflow.commerce.domain.RefundEligibility;
import com.lqq.supportflow.commerce.domain.Shipment;
import java.util.Map;
import org.springframework.stereotype.Service;

@Service
public class CommerceSupportToolService {
    private final QueryCustomerOrders orders; private final QueryShipment shipments; private final CheckRefundEligibility eligibility;
    public CommerceSupportToolService(QueryCustomerOrders orders, QueryShipment shipments, CheckRefundEligibility eligibility) { this.orders = orders; this.shipments = shipments; this.eligibility = eligibility; }

    public CommerceToolResult orderLookup(Long tenantId, Long customerId, String orderNo) {
        CustomerOrder order = orders.find(tenantId, customerId, orderNo).orElseThrow(() -> new IllegalArgumentException("order was not found"));
        return new CommerceToolResult("order.lookup", Map.of("orderNo", order.orderNo(), "status", order.status(), "totalAmount", order.totalAmount(), "currency", order.currency(), "createdAt", order.createdAt().toString()));
    }

    public CommerceToolResult shipmentTrack(Long tenantId, Long customerId, String orderNo) {
        Shipment shipment = shipments.find(tenantId, customerId, orderNo).orElseThrow(() -> new IllegalArgumentException("shipment was not found"));
        return new CommerceToolResult("shipment.track", Map.of("orderNo", shipment.orderNo(), "trackingNo", shipment.trackingNo(), "carrier", shipment.carrier(), "status", shipment.status(), "estimatedDeliveryAt", shipment.estimatedDeliveryAt().toString()));
    }

    public CommerceToolResult refundEligibility(Long tenantId, Long customerId, String orderNo) {
        RefundEligibility result = eligibility.check(tenantId, customerId, orderNo);
        return new CommerceToolResult("refund.checkEligibility", Map.of("orderNo", orderNo, "eligible", result.eligible(), "reason", result.reason()));
    }
}
