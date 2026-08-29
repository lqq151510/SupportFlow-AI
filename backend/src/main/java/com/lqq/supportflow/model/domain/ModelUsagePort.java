package com.lqq.supportflow.model.domain;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;

public interface ModelUsagePort {
    ModelUsageRecord save(Long tenantId, String scenario, String modelName, String protocol,
                          int inputTokens, int outputTokens, long latencyMs,
                          BigDecimal estimatedCostCny, BigDecimal estimatedCostUsd);

    List<ModelUsageRecord> listRecent(Long tenantId, int limit);

    UsageStatistics getStatistics(Long tenantId);

    record UsageStatistics(
            long totalCalls,
            long totalInputTokens,
            long totalOutputTokens,
            long totalTokens,
            long averageLatencyMs,
            BigDecimal totalEstimatedCostCny,
            BigDecimal totalEstimatedCostUsd,
            Map<String, Long> scenarioCalls,
            Map<String, Long> scenarioTokens,
            Map<String, Long> modelTokens,
            Map<String, BigDecimal> modelCostCny) {
    }
}
