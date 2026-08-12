package com.lqq.supportflow.action.application;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.lqq.supportflow.action.domain.Approval;
import com.lqq.supportflow.action.domain.ApprovalDecision;
import com.lqq.supportflow.action.domain.ApprovalPort;
import com.lqq.supportflow.action.domain.ApprovalRequestDetails;
import com.lqq.supportflow.action.domain.ApprovalStatus;
import com.lqq.supportflow.eventing.OutboxService;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ManageApprovalService {
    private static final int APPROVAL_EVENT_SCHEMA_VERSION = 1;
    private static final int EXECUTION_VERSION = 1;

    private final ApprovalPort approvals;
    private final OutboxService outbox;
    private final ObjectMapper json;

    public ManageApprovalService(ApprovalPort approvals, OutboxService outbox, ObjectMapper json) {
        this.approvals = approvals;
        this.outbox = outbox;
        this.json = json;
    }

    @Transactional
    public Approval create(Long tenantId, Long customerId, String actionType, String actionSummary,
                           ApprovalRequestDetails details, Long membershipId) {
        return approvals.create(tenantId, customerId, actionType, actionSummary, details, membershipId);
    }

    public List<Approval> list(Long tenantId) { return approvals.list(tenantId); }

    @Transactional
    public Approval decide(Long tenantId, Long approvalId, Long membershipId,
                           ApprovalStatus decision, String idempotencyKey) {
        ApprovalDecision result = approvals.decide(tenantId, approvalId, membershipId, decision, idempotencyKey);
        Approval approval = result.approval();
        if (result.newlyRecorded() && approval.status() == ApprovalStatus.APPROVED) {
            String businessKey = businessIdempotencyKey(approval);
            Map<String, Object> payload = new LinkedHashMap<>();
            payload.put("schemaVersion", APPROVAL_EVENT_SCHEMA_VERSION);
            payload.put("approvalId", approval.id().toString());
            payload.put("approvalVersion", approval.version());
            payload.put("executionVersion", EXECUTION_VERSION);
            payload.put("businessIdempotencyKey", businessKey);
            payload.put("actionType", approval.actionType());
            payload.put("orderNo", approval.orderNo());
            payload.put("amount", approval.amount());
            payload.put("currency", approval.currency());
            payload.put("eligibilityEvidence", approval.eligibilityEvidence());
            payload.put("decidedByMembershipId", approval.decidedByMembershipId().toString());
            outbox.record(tenantId, "approval.approved", "approval", approval.id().toString(), write(payload));
        }
        return approval;
    }

    @Transactional
    public Approval revoke(Long tenantId, Long approvalId, Long membershipId, String idempotencyKey) {
        return approvals.revoke(tenantId, approvalId, membershipId, idempotencyKey).approval();
    }

    private String businessIdempotencyKey(Approval approval) {
        return "approval:" + approval.id() + ":v" + approval.version() + ":execution:" + EXECUTION_VERSION;
    }

    private String write(Map<String, Object> payload) {
        try {
            return json.writeValueAsString(payload);
        } catch (JsonProcessingException exception) {
            throw new IllegalStateException("approval event could not be serialized", exception);
        }
    }
}
