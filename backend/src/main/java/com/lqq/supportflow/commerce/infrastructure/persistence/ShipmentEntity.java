package com.lqq.supportflow.commerce.infrastructure.persistence;
import com.baomidou.mybatisplus.annotation.IdType; import com.baomidou.mybatisplus.annotation.TableId; import com.baomidou.mybatisplus.annotation.TableName; import java.time.Instant;
@TableName("shipments") public class ShipmentEntity { @TableId(type=IdType.ASSIGN_ID) public Long id; public Long tenantId; public Long customerId; public String orderNo; public String trackingNo; public String carrier; public String status; public Instant estimatedDeliveryAt; public Instant createdAt; }
