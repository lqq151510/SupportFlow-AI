package com.lqq.supportflow.action.domain;

import java.util.List;

public interface ApprovalPort {
    Approval create(Long tenantId, Long customerId, String actionType, String actionSummary,
                    ApprovalRequestDetails details, Long requestedByMembershipId);
    List<Approval> list(Long tenantId);
    ApprovalDecision decide(Long tenantId, Long approvalId, Long membershipId,
                            ApprovalStatus decision, String idempotencyKey);
    ApprovalDecision revoke(Long tenantId, Long approvalId, Long membershipId, String idempotencyKey);
}
