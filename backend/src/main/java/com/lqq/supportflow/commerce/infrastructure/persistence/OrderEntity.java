package com.lqq.supportflow.commerce.infrastructure.persistence;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import java.math.BigDecimal;
import java.time.Instant;

@TableName("orders")
public class OrderEntity {

    @TableId(type = IdType.ASSIGN_ID)
    public Long id;
    public Long tenantId;
    public Long customerId;
    public String orderNo;
    public String status;
    public BigDecimal totalAmount;
    public String currency;
    public Instant createdAt;
    public Instant updatedAt;
}
