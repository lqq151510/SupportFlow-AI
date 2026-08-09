package com.lqq.supportflow.identity.infrastructure.persistence;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import java.time.Instant;

@TableName("tenant_memberships")
public class TenantMembershipEntity {
    @TableId(type = IdType.ASSIGN_ID) public Long id;
    public Long tenantId; public Long userId; public String role; public String status; public Instant createdAt; public Instant updatedAt;
}
