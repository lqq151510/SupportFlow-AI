package com.lqq.supportflow.model.infrastructure.persistence;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.lqq.supportflow.model.domain.ModelUsagePort;
import com.lqq.supportflow.model.domain.ModelUsageRecord;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Component;

@Component
public class MyBatisModelUsageAdapter implements ModelUsagePort {

    private final ModelUsageMapper mapper;

    public MyBatisModelUsageAdapter(ModelUsageMapper mapper) {
        this.mapper = mapper;
    }

    @Override
    public ModelUsageRecord save(Long tenantId, String scenario, String modelName, String protocol,
                                  int inputTokens, int outputTokens, long latencyMs,
                                  BigDecimal estimatedCostCny, BigDecimal estimatedCostUsd) {
        ModelUsageEntity entity = new ModelUsageEntity();
        entity.tenantId = tenantId;
        entity.scenario = scenario;
        entity.modelName = modelName;
        entity.protocol = protocol;
        entity.inputTokens = inputTokens;
        entity.outputTokens = outputTokens;
        entity.totalTokens = inputTokens + outputTokens;
        entity.latencyMs = latencyMs;
        entity.estimatedCostCny = estimatedCostCny;
        entity.estimatedCostUsd = estimatedCostUsd;
        entity.createdAt = Instant.now();
        mapper.insert(entity);

        return toRecord(entity);
    }

    @Override
    public List<ModelUsageRecord> listRecent(Long tenantId, int limit) {
        return mapper.selectList(new QueryWrapper<ModelUsageEntity>()
                        .eq("tenant_id", tenantId)
                        .orderByDesc("created_at")
                        .last("LIMIT " + Math.max(1, Math.min(limit, 100))))
                .stream().map(this::toRecord).toList();
    }

    @Override
    public UsageStatistics getStatistics(Long tenantId) {
        List<ModelUsageEntity> list = mapper.selectList(new QueryWrapper<ModelUsageEntity>().eq("tenant_id", tenantId));

        long totalCalls = list.size();
        long totalInputTokens = 0;
        long totalOutputTokens = 0;
        long totalTokens = 0;
        long totalLatency = 0;
        BigDecimal totalCostCny = BigDecimal.ZERO;
        BigDecimal totalCostUsd = BigDecimal.ZERO;

        Map<String, Long> scenarioCalls = new HashMap<>();
        Map<String, Long> scenarioTokens = new HashMap<>();
        Map<String, Long> modelTokens = new HashMap<>();
        Map<String, BigDecimal> modelCostCny = new HashMap<>();

        for (ModelUsageEntity item : list) {
            int input = item.inputTokens == null ? 0 : item.inputTokens;
            int output = item.outputTokens == null ? 0 : item.outputTokens;
            int total = item.totalTokens == null ? (input + output) : item.totalTokens;
            long latency = item.latencyMs == null ? 0 : item.latencyMs;
            BigDecimal cny = item.estimatedCostCny == null ? BigDecimal.ZERO : item.estimatedCostCny;
            BigDecimal usd = item.estimatedCostUsd == null ? BigDecimal.ZERO : item.estimatedCostUsd;

            totalInputTokens += input;
            totalOutputTokens += output;
            totalTokens += total;
            totalLatency += latency;
            totalCostCny = totalCostCny.add(cny);
            totalCostUsd = totalCostUsd.add(usd);

            String sc = item.scenario == null ? "OTHER" : item.scenario;
            scenarioCalls.merge(sc, 1L, Long::sum);
            scenarioTokens.merge(sc, (long) total, Long::sum);

            String model = item.modelName == null ? "unknown" : item.modelName;
            modelTokens.merge(model, (long) total, Long::sum);
            modelCostCny.merge(model, cny, BigDecimal::add);
        }

        long averageLatencyMs = totalCalls == 0 ? 0 : (totalLatency / totalCalls);

        return new UsageStatistics(
                totalCalls,
                totalInputTokens,
                totalOutputTokens,
                totalTokens,
                averageLatencyMs,
                totalCostCny,
                totalCostUsd,
                scenarioCalls,
                scenarioTokens,
                modelTokens,
                modelCostCny
        );
    }

    private ModelUsageRecord toRecord(ModelUsageEntity entity) {
        return new ModelUsageRecord(
                entity.id,
                entity.tenantId,
                entity.scenario,
                entity.modelName,
                entity.protocol,
                entity.inputTokens == null ? 0 : entity.inputTokens,
                entity.outputTokens == null ? 0 : entity.outputTokens,
                entity.totalTokens == null ? 0 : entity.totalTokens,
                entity.latencyMs == null ? 0 : entity.latencyMs,
                entity.estimatedCostCny == null ? BigDecimal.ZERO : entity.estimatedCostCny,
                entity.estimatedCostUsd == null ? BigDecimal.ZERO : entity.estimatedCostUsd,
                entity.createdAt
        );
    }
}
