package com.lqq.supportflow.action.api;
import jakarta.validation.constraints.NotBlank;
public record CreateApprovalRequest(@NotBlank String actionType,@NotBlank String actionSummary) { }
