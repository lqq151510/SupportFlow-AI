package com.lqq.supportflow.model.domain;

import java.math.BigDecimal;
import java.math.RoundingMode;

public final class ModelPricingCalculator {

    private static final BigDecimal MILLION = new BigDecimal("1000000");
    private static final BigDecimal USD_TO_CNY_RATE = new BigDecimal("7.2");

    public record EstimatedCost(BigDecimal costCny, BigDecimal costUsd) { }

    private ModelPricingCalculator() { }

    public static EstimatedCost estimate(String modelName, int inputTokens, int outputTokens) {
        String normalized = modelName == null ? "" : modelName.trim().toLowerCase();

        BigDecimal inputPricePerMillionCny;
        BigDecimal outputPricePerMillionCny;

        if (normalized.contains("deepseek-reasoner") || normalized.contains("deepseek-r1") || normalized.contains("r1")) {
            inputPricePerMillionCny = new BigDecimal("4.00");
            outputPricePerMillionCny = new BigDecimal("16.00");
        } else if (normalized.contains("deepseek")) {
            inputPricePerMillionCny = new BigDecimal("1.00");
            outputPricePerMillionCny = new BigDecimal("2.00");
        } else if (normalized.contains("gpt-4o-mini")) {
            BigDecimal inputUsd = new BigDecimal("0.15");
            BigDecimal outputUsd = new BigDecimal("0.60");
            inputPricePerMillionCny = inputUsd.multiply(USD_TO_CNY_RATE);
            outputPricePerMillionCny = outputUsd.multiply(USD_TO_CNY_RATE);
        } else if (normalized.contains("gpt-4o") || normalized.contains("gpt-4")) {
            BigDecimal inputUsd = new BigDecimal("2.50");
            BigDecimal outputUsd = new BigDecimal("10.00");
            inputPricePerMillionCny = inputUsd.multiply(USD_TO_CNY_RATE);
            outputPricePerMillionCny = outputUsd.multiply(USD_TO_CNY_RATE);
        } else if (normalized.contains("o1") || normalized.contains("o3")) {
            BigDecimal inputUsd = new BigDecimal("1.10");
            BigDecimal outputUsd = new BigDecimal("4.40");
            inputPricePerMillionCny = inputUsd.multiply(USD_TO_CNY_RATE);
            outputPricePerMillionCny = outputUsd.multiply(USD_TO_CNY_RATE);
        } else if (normalized.contains("claude")) {
            BigDecimal inputUsd = new BigDecimal("3.00");
            BigDecimal outputUsd = new BigDecimal("15.00");
            inputPricePerMillionCny = inputUsd.multiply(USD_TO_CNY_RATE);
            outputPricePerMillionCny = outputUsd.multiply(USD_TO_CNY_RATE);
        } else {
            inputPricePerMillionCny = new BigDecimal("0.50");
            outputPricePerMillionCny = new BigDecimal("1.00");
        }

        BigDecimal inputCny = inputPricePerMillionCny
                .multiply(BigDecimal.valueOf(Math.max(0, inputTokens)))
                .divide(MILLION, 6, RoundingMode.HALF_UP);
        BigDecimal outputCny = outputPricePerMillionCny
                .multiply(BigDecimal.valueOf(Math.max(0, outputTokens)))
                .divide(MILLION, 6, RoundingMode.HALF_UP);
        BigDecimal totalCny = inputCny.add(outputCny).setScale(6, RoundingMode.HALF_UP);
        BigDecimal totalUsd = totalCny.divide(USD_TO_CNY_RATE, 6, RoundingMode.HALF_UP);

        return new EstimatedCost(totalCny, totalUsd);
    }
}
