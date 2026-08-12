package com.lqq.supportflow.action.domain;

import java.math.BigDecimal;

public record ApprovalRequestDetails(
        String orderNo,
        BigDecimal amount,
        String currency,
        String eligibilityEvidence
) { }
