package com.lqq.supportflow.action.infrastructure.persistence;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.annotation.Version;
import java.math.BigDecimal;
import java.time.Instant;

@TableName("approval_requests")
public class ApprovalEntity {
    @TableId(type = IdType.ASSIGN_ID) public Long id;
    public Long tenantId;
    public Long customerId;
    public String actionType;
    public String actionSummary;
    public String orderNo;
    public BigDecimal amount;
    public String currency;
    public String eligibilityEvidence;
    public String status;
    public Long requestedByMembershipId;
    public Long decidedByMembershipId;
    public Instant expiresAt;
    @Version public Long version;
    public Instant createdAt;
    public Instant updatedAt;
}
