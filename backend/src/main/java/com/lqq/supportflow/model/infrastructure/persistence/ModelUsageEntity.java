package com.lqq.supportflow.model.infrastructure.persistence;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import java.math.BigDecimal;
import java.time.Instant;

@TableName("model_usage_records")
public class ModelUsageEntity {
    @TableId(type = IdType.ASSIGN_ID)
    public Long id;
    public Long tenantId;
    public String scenario;
    public String modelName;
    public String protocol;
    public Integer inputTokens;
    public Integer outputTokens;
    public Integer totalTokens;
    public Long latencyMs;
    public BigDecimal estimatedCostCny;
    public BigDecimal estimatedCostUsd;
    public Instant createdAt;
}
