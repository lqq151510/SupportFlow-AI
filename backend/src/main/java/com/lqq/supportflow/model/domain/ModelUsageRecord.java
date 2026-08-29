package com.lqq.supportflow.model.domain;

import com.fasterxml.jackson.databind.annotation.JsonSerialize;
import com.fasterxml.jackson.databind.ser.std.ToStringSerializer;
import java.math.BigDecimal;
import java.time.Instant;

public record ModelUsageRecord(
        @JsonSerialize(using = ToStringSerializer.class) Long id,
        @JsonSerialize(using = ToStringSerializer.class) Long tenantId,
        String scenario,
        String modelName,
        String protocol,
        int inputTokens,
        int outputTokens,
        int totalTokens,
        long latencyMs,
        BigDecimal estimatedCostCny,
        BigDecimal estimatedCostUsd,
        Instant createdAt) {
}
