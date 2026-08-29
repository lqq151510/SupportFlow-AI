package com.lqq.supportflow;

import static org.junit.jupiter.api.Assertions.*;

import com.lqq.supportflow.model.ModelUsageService;
import com.lqq.supportflow.model.domain.ModelUsagePort;
import com.lqq.supportflow.model.domain.ModelUsageRecord;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

class ModelUsageServiceTest {

    static class InMemoryModelUsagePort implements ModelUsagePort {
        private final List<ModelUsageRecord> list = new ArrayList<>();
        private long seq = 1;

        @Override
        public ModelUsageRecord save(Long tenantId, String scenario, String modelName, String protocol,
                                      int inputTokens, int outputTokens, long latencyMs,
                                      BigDecimal estimatedCostCny, BigDecimal estimatedCostUsd) {
            ModelUsageRecord record = new ModelUsageRecord(
                    seq++, tenantId, scenario, modelName, protocol,
                    inputTokens, outputTokens, inputTokens + outputTokens,
                    latencyMs, estimatedCostCny, estimatedCostUsd, Instant.now());
            list.add(record);
            return record;
        }

        @Override
        public List<ModelUsageRecord> listRecent(Long tenantId, int limit) {
            return list.stream().filter(r -> r.tenantId().equals(tenantId)).limit(limit).toList();
        }

        @Override
        public UsageStatistics getStatistics(Long tenantId) {
            List<ModelUsageRecord> tenantList = list.stream().filter(r -> r.tenantId().equals(tenantId)).toList();
            long totalInput = tenantList.stream().mapToLong(ModelUsageRecord::inputTokens).sum();
            long totalOutput = tenantList.stream().mapToLong(ModelUsageRecord::outputTokens).sum();
            BigDecimal totalCny = tenantList.stream().map(ModelUsageRecord::estimatedCostCny).reduce(BigDecimal.ZERO, BigDecimal::add);
            BigDecimal totalUsd = tenantList.stream().map(ModelUsageRecord::estimatedCostUsd).reduce(BigDecimal.ZERO, BigDecimal::add);
            Map<String, Long> scenarios = new HashMap<>();
            tenantList.forEach(r -> scenarios.merge(r.scenario(), 1L, Long::sum));
            return new UsageStatistics(tenantList.size(), totalInput, totalOutput, totalInput + totalOutput,
                    150, totalCny, totalUsd, scenarios, Map.of(), Map.of(), Map.of());
        }
    }

    @Test
    void recordsAndSummarizesUsage() {
        InMemoryModelUsagePort port = new InMemoryModelUsagePort();
        ModelUsageService service = new ModelUsageService(port);

        service.recordUsage(100L, "CHAT", "deepseek-chat", "STREAM", 1000, 500, 200);
        service.recordUsage(100L, "KNOWLEDGE_ORGANIZATION", "gpt-4o", "SYNC", 2000, 1000, 450);

        ModelUsagePort.UsageStatistics stats = service.getUsageStatistics(100L);
        assertEquals(2, stats.totalCalls());
        assertEquals(3000, stats.totalInputTokens());
        assertEquals(1500, stats.totalOutputTokens());
        assertEquals(4500, stats.totalTokens());
        assertTrue(stats.totalEstimatedCostCny().compareTo(BigDecimal.ZERO) > 0);
        assertEquals(2, service.listRecentUsages(100L, 10).size());
    }
}
