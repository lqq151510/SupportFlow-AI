package com.lqq.supportflow.action.infrastructure.persistence;
import com.baomidou.mybatisplus.annotation.*; import java.time.Instant;
@TableName("approval_decisions") public class ApprovalDecisionEntity { @TableId(type=IdType.ASSIGN_ID) public Long id; public Long tenantId; public Long approvalId; public String idempotencyKey; public String decision; public Instant createdAt; }
