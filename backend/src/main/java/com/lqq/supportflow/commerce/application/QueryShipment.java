package com.lqq.supportflow.commerce.application;
import com.lqq.supportflow.commerce.domain.Shipment; import com.lqq.supportflow.commerce.domain.ShipmentPort; import java.util.Optional; import org.springframework.stereotype.Service;
@Service public class QueryShipment { private final ShipmentPort shipments; public QueryShipment(ShipmentPort shipments){this.shipments=shipments;} public Optional<Shipment> find(Long tenantId,Long customerId,String orderNo){return shipments.find(tenantId,customerId,orderNo);} }
