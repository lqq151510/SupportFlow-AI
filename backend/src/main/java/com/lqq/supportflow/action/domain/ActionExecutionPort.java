package com.lqq.supportflow.action.domain;

public interface ActionExecutionPort {
    boolean executeOnce(Long tenantId, Long approvalId, String actionType,
                        long executionVersion, String businessIdempotencyKey);
}
