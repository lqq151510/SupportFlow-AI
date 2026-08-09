package com.lqq.supportflow.action.api;
import com.lqq.supportflow.action.domain.ApprovalStatus; import jakarta.validation.constraints.NotNull;
public record DecisionRequest(@NotNull ApprovalStatus decision) { }
