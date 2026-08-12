package com.lqq.supportflow.action.api;

import com.lqq.supportflow.action.application.ManageApprovalService;
import com.lqq.supportflow.action.domain.Approval;
import com.lqq.supportflow.action.domain.ApprovalRequestDetails;
import com.lqq.supportflow.shared.AuthenticatedPrincipal;
import jakarta.validation.Valid;
import java.util.List;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/admin/approvals")
public class AdminApprovalController {
    private final ManageApprovalService service;

    public AdminApprovalController(ManageApprovalService service) { this.service = service; }

    @GetMapping
    List<Approval> list(@AuthenticationPrincipal AuthenticatedPrincipal principal) {
        return service.list(principal.tenantId());
    }

    @PostMapping
    ResponseEntity<Approval> create(@AuthenticationPrincipal AuthenticatedPrincipal principal,
                                    @Valid @RequestBody CreateApprovalRequest request) {
        ApprovalRequestDetails details = new ApprovalRequestDetails(
                request.orderNo(), request.amount(), request.currency(), request.eligibilityEvidence());
        return ResponseEntity.status(HttpStatus.CREATED).body(service.create(
                principal.tenantId(), null, request.actionType(), request.actionSummary(),
                details, principal.membershipId()));
    }

    @PostMapping("/{approvalId}/decision")
    Approval decide(@AuthenticationPrincipal AuthenticatedPrincipal principal,
                    @PathVariable Long approvalId,
                    @RequestHeader("Idempotency-Key") String idempotencyKey,
                    @Valid @RequestBody DecisionRequest request) {
        return service.decide(principal.tenantId(), approvalId, principal.membershipId(),
                request.decision(), idempotencyKey);
    }

    @PostMapping("/{approvalId}/revoke")
    Approval revoke(@AuthenticationPrincipal AuthenticatedPrincipal principal,
                    @PathVariable Long approvalId,
                    @RequestHeader("Idempotency-Key") String idempotencyKey) {
        return service.revoke(principal.tenantId(), approvalId, principal.membershipId(), idempotencyKey);
    }
}
