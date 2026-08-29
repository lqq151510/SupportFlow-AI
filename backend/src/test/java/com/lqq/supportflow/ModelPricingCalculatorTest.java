package com.lqq.supportflow;

import static org.junit.jupiter.api.Assertions.*;

import com.lqq.supportflow.model.domain.ModelPricingCalculator;
import java.math.BigDecimal;
import org.junit.jupiter.api.Test;

class ModelPricingCalculatorTest {

    @Test
    void estimatesDeepSeekChatCostAccurately() {
        // deepseek-chat: input 1.00/1M, output 2.00/1M
        ModelPricingCalculator.EstimatedCost cost = ModelPricingCalculator.estimate("deepseek-chat", 1_000_000, 500_000);
        // input 1.00 + output 1.00 = 2.00 CNY
        assertEquals(new BigDecimal("2.000000"), cost.costCny());
        assertTrue(cost.costUsd().compareTo(BigDecimal.ZERO) > 0);
    }

    @Test
    void estimatesDeepSeekReasonerCost() {
        // deepseek-reasoner: input 4.00/1M, output 16.00/1M
        ModelPricingCalculator.EstimatedCost cost = ModelPricingCalculator.estimate("deepseek-reasoner", 500_000, 250_000);
        // input 2.00 + output 4.00 = 6.00 CNY
        assertEquals(new BigDecimal("6.000000"), cost.costCny());
    }

    @Test
    void estimatesGpt4oMiniCost() {
        ModelPricingCalculator.EstimatedCost cost = ModelPricingCalculator.estimate("gpt-4o-mini", 100_000, 50_000);
        assertTrue(cost.costCny().compareTo(BigDecimal.ZERO) > 0);
        assertTrue(cost.costUsd().compareTo(BigDecimal.ZERO) > 0);
    }

    @Test
    void handlesZeroOrNegativeTokensGracefully() {
        ModelPricingCalculator.EstimatedCost cost = ModelPricingCalculator.estimate("gpt-4o", 0, -10);
        assertEquals(new BigDecimal("0.000000"), cost.costCny());
        assertEquals(new BigDecimal("0.000000"), cost.costUsd());
    }

    @Test
    void supportsEveryConfiguredProviderFamilyAndTheFallbackRate() {
        for (String model : java.util.List.of("gpt-4o", "gpt-4-turbo", "o1-mini", "o3-mini", "claude-3-5-sonnet", "custom-model")) {
            ModelPricingCalculator.EstimatedCost cost = ModelPricingCalculator.estimate(model, 1_000_000, 1_000_000);
            assertTrue(cost.costCny().compareTo(BigDecimal.ZERO) > 0, model);
            assertTrue(cost.costUsd().compareTo(BigDecimal.ZERO) > 0, model);
        }
        assertTrue(ModelPricingCalculator.estimate(null, 1, 1).costCny().compareTo(BigDecimal.ZERO) > 0);
    }
}
