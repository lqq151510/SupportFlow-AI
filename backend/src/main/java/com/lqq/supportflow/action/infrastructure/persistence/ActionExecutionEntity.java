package com.lqq.supportflow.action.infrastructure.persistence;
import com.baomidou.mybatisplus.annotation.*; import java.time.Instant;
@TableName("action_executions") public class ActionExecutionEntity { @TableId(type=IdType.ASSIGN_ID) public Long id; public Long tenantId; public Long approvalId; public String actionType; public Long executionVersion; public String businessIdempotencyKey; public String status; public Instant executedAt; }
