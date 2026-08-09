package com.lqq.supportflow.action.domain;
import java.util.List;
public interface ApprovalPort { Approval create(Long tenantId,Long customerId,String actionType,String actionSummary,Long requestedByMembershipId); List<Approval> list(Long tenantId); Approval decide(Long tenantId,Long approvalId,Long membershipId,ApprovalStatus decision,String idempotencyKey); }
