package com.lqq.supportflow.model;

import com.lqq.supportflow.model.domain.ModelPricingCalculator;
import com.lqq.supportflow.model.domain.ModelUsagePort;
import com.lqq.supportflow.model.domain.ModelUsageRecord;
import java.util.List;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ModelUsageService {

    private final ModelUsagePort usages;

    public ModelUsageService(ModelUsagePort usages) {
        this.usages = usages;
    }

    @Transactional
    public ModelUsageRecord recordUsage(Long tenantId, String scenario, String modelName, String protocol,
                                        int inputTokens, int outputTokens, long latencyMs) {
        ModelPricingCalculator.EstimatedCost cost = ModelPricingCalculator.estimate(modelName, inputTokens, outputTokens);
        return usages.save(tenantId, scenario, modelName, protocol, inputTokens, outputTokens, latencyMs,
                cost.costCny(), cost.costUsd());
    }

    @Transactional(readOnly = true)
    public ModelUsagePort.UsageStatistics getUsageStatistics(Long tenantId) {
        return usages.getStatistics(tenantId);
    }

    @Transactional(readOnly = true)
    public List<ModelUsageRecord> listRecentUsages(Long tenantId, int limit) {
        return usages.listRecent(tenantId, limit);
    }
}
