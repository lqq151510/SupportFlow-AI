package com.lqq.supportflow.action.api;

import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import java.math.BigDecimal;

public record CreateApprovalRequest(
        @NotBlank String actionType,
        @NotBlank String actionSummary,
        @NotBlank String orderNo,
        @NotNull @DecimalMin("0.01") BigDecimal amount,
        @NotBlank @Pattern(regexp = "[A-Za-z]{3}") String currency,
        @NotBlank String eligibilityEvidence
) { }
