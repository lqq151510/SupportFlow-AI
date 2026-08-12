package com.lqq.supportflow.action.infrastructure.persistence;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.UpdateWrapper;
import com.lqq.supportflow.action.domain.Approval;
import com.lqq.supportflow.action.domain.ApprovalDecision;
import com.lqq.supportflow.action.domain.ApprovalPort;
import com.lqq.supportflow.action.domain.ApprovalRequestDetails;
import com.lqq.supportflow.action.domain.ApprovalStatus;
import com.lqq.supportflow.shared.ConflictException;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import org.springframework.stereotype.Component;

@Component
public class MyBatisApprovalAdapter implements ApprovalPort {
    private final ApprovalMapper approvals;
    private final ApprovalDecisionMapper decisions;

    public MyBatisApprovalAdapter(ApprovalMapper approvals, ApprovalDecisionMapper decisions) {
        this.approvals = approvals;
        this.decisions = decisions;
    }

    @Override
    public Approval create(Long tenantId, Long customerId, String actionType, String actionSummary,
                           ApprovalRequestDetails details, Long requestedByMembershipId) {
        Instant now = Instant.now();
        ApprovalEntity entity = new ApprovalEntity();
        entity.tenantId = tenantId;
        entity.customerId = customerId;
        entity.actionType = actionType;
        entity.actionSummary = actionSummary;
        entity.orderNo = details.orderNo();
        entity.amount = details.amount();
        entity.currency = details.currency().toUpperCase(java.util.Locale.ROOT);
        entity.eligibilityEvidence = details.eligibilityEvidence();
        entity.status = ApprovalStatus.PENDING.name();
        entity.requestedByMembershipId = requestedByMembershipId;
        entity.expiresAt = now.plus(Duration.ofMinutes(30));
        entity.version = 0L;
        entity.createdAt = now;
        entity.updatedAt = now;
        approvals.insert(entity);
        return approval(entity);
    }

    @Override
    public List<Approval> list(Long tenantId) {
        expireOutstanding(tenantId);
        return approvals.selectList(new QueryWrapper<ApprovalEntity>()
                        .eq("tenant_id", tenantId).orderByDesc("created_at"))
                .stream().map(this::approval).toList();
    }

    @Override
    public ApprovalDecision decide(Long tenantId, Long approvalId, Long membershipId,
                                   ApprovalStatus decision, String idempotencyKey) {
        if (decision != ApprovalStatus.APPROVED && decision != ApprovalStatus.REJECTED) {
            throw new IllegalArgumentException("approval decision must be APPROVED or REJECTED");
        }
        return transition(tenantId, approvalId, membershipId, decision, idempotencyKey);
    }

    @Override
    public ApprovalDecision revoke(Long tenantId, Long approvalId, Long membershipId, String idempotencyKey) {
        return transition(tenantId, approvalId, membershipId, ApprovalStatus.REVOKED, idempotencyKey);
    }

    private ApprovalDecision transition(Long tenantId, Long approvalId, Long membershipId,
                                        ApprovalStatus decision, String idempotencyKey) {
        if (idempotencyKey == null || idempotencyKey.isBlank()) {
            throw new IllegalArgumentException("Idempotency-Key is required");
        }
        ApprovalDecisionEntity previous = decisions.selectOne(new QueryWrapper<ApprovalDecisionEntity>()
                .eq("tenant_id", tenantId).eq("approval_id", approvalId)
                .eq("idempotency_key", idempotencyKey));
        if (previous != null) {
            if (!decision.name().equals(previous.decision)) {
                throw new ConflictException("Idempotency-Key was already used for a different approval decision");
            }
            return new ApprovalDecision(approval(owned(tenantId, approvalId)), false);
        }

        ApprovalEntity source = owned(tenantId, approvalId);
        if (source.expiresAt.isBefore(Instant.now())) {
            expire(tenantId, approvalId);
            return new ApprovalDecision(approval(owned(tenantId, approvalId)), false);
        }
        if (!ApprovalStatus.PENDING.name().equals(source.status)) {
            throw new ConflictException("approval is not pending");
        }
        int updated = approvals.update(new ApprovalEntity(), new UpdateWrapper<ApprovalEntity>()
                .eq("id", approvalId).eq("tenant_id", tenantId).eq("version", source.version)
                .eq("status", ApprovalStatus.PENDING.name())
                .set("status", decision.name()).set("decided_by_membership_id", membershipId)
                .set("updated_at", Instant.now()).setSql("version = version + 1"));
        if (updated != 1) throw new ConflictException("approval changed concurrently");

        ApprovalDecisionEntity saved = new ApprovalDecisionEntity();
        saved.tenantId = tenantId;
        saved.approvalId = approvalId;
        saved.idempotencyKey = idempotencyKey;
        saved.decision = decision.name();
        saved.approvalVersion = source.version + 1;
        saved.createdAt = Instant.now();
        decisions.insert(saved);
        return new ApprovalDecision(approval(owned(tenantId, approvalId)), true);
    }

    private void expireOutstanding(Long tenantId) {
        approvals.update(new ApprovalEntity(), new UpdateWrapper<ApprovalEntity>()
                .eq("tenant_id", tenantId).eq("status", ApprovalStatus.PENDING.name())
                .lt("expires_at", Instant.now()).set("status", ApprovalStatus.EXPIRED.name())
                .set("updated_at", Instant.now()).setSql("version = version + 1"));
    }

    private void expire(Long tenantId, Long id) {
        approvals.update(new ApprovalEntity(), new UpdateWrapper<ApprovalEntity>()
                .eq("id", id).eq("tenant_id", tenantId).eq("status", ApprovalStatus.PENDING.name())
                .set("status", ApprovalStatus.EXPIRED.name()).set("updated_at", Instant.now())
                .setSql("version = version + 1"));
    }

    private ApprovalEntity owned(Long tenantId, Long id) {
        ApprovalEntity entity = approvals.selectOne(new QueryWrapper<ApprovalEntity>()
                .eq("id", id).eq("tenant_id", tenantId));
        if (entity == null) throw new IllegalArgumentException("approval does not belong to tenant");
        return entity;
    }

    private Approval approval(ApprovalEntity entity) {
        return new Approval(entity.id, entity.actionType, entity.actionSummary, entity.orderNo,
                entity.amount, entity.currency, entity.eligibilityEvidence,
                entity.requestedByMembershipId, entity.decidedByMembershipId,
                entity.version, ApprovalStatus.valueOf(entity.status), entity.expiresAt);
    }
}
