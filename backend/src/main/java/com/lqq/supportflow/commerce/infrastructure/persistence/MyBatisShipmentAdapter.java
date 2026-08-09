package com.lqq.supportflow.commerce.infrastructure.persistence;
import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper; import com.lqq.supportflow.commerce.domain.Shipment; import com.lqq.supportflow.commerce.domain.ShipmentPort; import java.time.Instant; import java.util.Optional; import org.springframework.stereotype.Component;
@Component public class MyBatisShipmentAdapter implements ShipmentPort {
 private final ShipmentMapper mapper; public MyBatisShipmentAdapter(ShipmentMapper mapper){this.mapper=mapper;}
 public void createDemo(Long tenantId,Long customerId){ ShipmentEntity e=new ShipmentEntity(); e.tenantId=tenantId;e.customerId=customerId;e.orderNo="DEMO-001";e.trackingNo="SF-DEMO-001";e.carrier="SF Express";e.status="IN_TRANSIT";e.estimatedDeliveryAt=Instant.now().plus(java.time.Duration.ofDays(2));e.createdAt=Instant.now();mapper.insert(e); }
 public Optional<Shipment> find(Long tenantId,Long customerId,String orderNo){return Optional.ofNullable(mapper.selectOne(new QueryWrapper<ShipmentEntity>().eq("tenant_id",tenantId).eq("customer_id",customerId).eq("order_no",orderNo))).map(e->new Shipment(e.orderNo,e.trackingNo,e.carrier,e.status,e.estimatedDeliveryAt));}
}
