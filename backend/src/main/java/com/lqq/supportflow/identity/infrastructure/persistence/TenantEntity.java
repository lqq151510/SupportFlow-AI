package com.lqq.supportflow.identity.infrastructure.persistence;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import java.time.Instant;

@TableName("tenants")
public class TenantEntity {
    @TableId(type = IdType.ASSIGN_ID) public Long id;
    public String code; public String name; public String status; public Instant createdAt; public Instant updatedAt;
}
