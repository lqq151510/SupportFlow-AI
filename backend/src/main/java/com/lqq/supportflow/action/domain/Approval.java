package com.lqq.supportflow.action.domain;
import java.time.Instant;
public record Approval(Long id,String actionType,String actionSummary,ApprovalStatus status,Instant expiresAt) { }
