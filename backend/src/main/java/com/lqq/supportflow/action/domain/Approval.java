package com.lqq.supportflow.action.domain;

import com.fasterxml.jackson.databind.annotation.JsonSerialize;
import com.fasterxml.jackson.databind.ser.std.ToStringSerializer;
import java.math.BigDecimal;
import java.time.Instant;

public record Approval(
        @JsonSerialize(using = ToStringSerializer.class) Long id,
        String actionType,
        String actionSummary,
        String orderNo,
        BigDecimal amount,
        String currency,
        String eligibilityEvidence,
        @JsonSerialize(using = ToStringSerializer.class) Long requestedByMembershipId,
        @JsonSerialize(using = ToStringSerializer.class) Long decidedByMembershipId,
        long version,
        ApprovalStatus status,
        Instant expiresAt
) { }
