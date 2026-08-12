package com.lqq.supportflow;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.lqq.supportflow.action.domain.ApprovalStatus;
import com.lqq.supportflow.action.domain.ApprovalRequestDetails;
import com.lqq.supportflow.action.infrastructure.persistence.ApprovalDecisionEntity;
import com.lqq.supportflow.action.infrastructure.persistence.ApprovalDecisionMapper;
import com.lqq.supportflow.action.infrastructure.persistence.ApprovalEntity;
import com.lqq.supportflow.action.infrastructure.persistence.ApprovalMapper;
import com.lqq.supportflow.action.infrastructure.persistence.MyBatisApprovalAdapter;
import com.lqq.supportflow.shared.ConflictException;
import java.time.Instant;
import java.math.BigDecimal;
import java.util.List;
import org.junit.jupiter.api.Test;

class MyBatisApprovalAdapterTest {

    @Test
    void createsListsAndApprovesPendingRequests() {
        ApprovalMapper approvals = mock(ApprovalMapper.class);
        ApprovalDecisionMapper decisions = mock(ApprovalDecisionMapper.class);
        ApprovalEntity pending = approval(ApprovalStatus.PENDING, Instant.now().plusSeconds(60));
        when(approvals.selectList(any())).thenReturn(List.of(pending));
        when(decisions.selectOne(any())).thenReturn(null);
        when(approvals.selectOne(any())).thenReturn(pending);
        when(approvals.update(any(), any())).thenReturn(1);
        MyBatisApprovalAdapter adapter = new MyBatisApprovalAdapter(approvals, decisions);

        assertThat(adapter.create(7L, 8L, "refund", "refund order",
                details(), 9L).status()).isEqualTo(ApprovalStatus.PENDING);
        assertThat(adapter.list(7L)).extracting(item -> item.status()).containsExactly(ApprovalStatus.PENDING);
        assertThat(adapter.decide(7L, 10L, 9L, ApprovalStatus.APPROVED, "key").newlyRecorded()).isTrue();
        verify(decisions).insert(any(ApprovalDecisionEntity.class));
    }

    @Test
    void returnsPriorDecisionExpiresStaleRequestsAndRejectsInvalidState() {
        ApprovalMapper approvals = mock(ApprovalMapper.class);
        ApprovalDecisionMapper decisions = mock(ApprovalDecisionMapper.class);
        ApprovalEntity pending = approval(ApprovalStatus.PENDING, Instant.now().plusSeconds(60));
        ApprovalDecisionEntity prior = new ApprovalDecisionEntity();
        prior.decision = ApprovalStatus.APPROVED.name();
        when(decisions.selectOne(any())).thenReturn(prior, null, null, null);
        when(approvals.selectOne(any())).thenReturn(pending, approval(ApprovalStatus.PENDING, Instant.now().minusSeconds(1)), approval(ApprovalStatus.APPROVED, Instant.now().plusSeconds(60)));
        MyBatisApprovalAdapter adapter = new MyBatisApprovalAdapter(approvals, decisions);

        assertThat(adapter.decide(7L, 10L, 9L, ApprovalStatus.APPROVED, "same").newlyRecorded()).isFalse();
        assertThat(adapter.decide(7L, 10L, 9L, ApprovalStatus.REJECTED, "expired").newlyRecorded()).isFalse();
        assertThatThrownBy(() -> adapter.decide(7L, 10L, 9L, ApprovalStatus.REJECTED, "settled"))
                .isInstanceOf(ConflictException.class).hasMessage("approval is not pending");
        assertThatThrownBy(() -> adapter.decide(7L, 10L, 9L, ApprovalStatus.EXPIRED, "invalid"))
                .isInstanceOf(IllegalArgumentException.class).hasMessage("approval decision must be APPROVED or REJECTED");
    }

    @Test
    void rejectsConcurrentAndForeignApprovalDecisions() {
        ApprovalMapper approvals = mock(ApprovalMapper.class);
        ApprovalDecisionMapper decisions = mock(ApprovalDecisionMapper.class);
        when(decisions.selectOne(any())).thenReturn(null);
        when(approvals.selectOne(any())).thenReturn(approval(ApprovalStatus.PENDING, Instant.now().plusSeconds(60)), (ApprovalEntity) null);
        when(approvals.update(any(), any())).thenReturn(0);
        MyBatisApprovalAdapter adapter = new MyBatisApprovalAdapter(approvals, decisions);

        assertThatThrownBy(() -> adapter.decide(7L, 10L, 9L, ApprovalStatus.APPROVED, "conflict"))
                .isInstanceOf(ConflictException.class).hasMessage("approval changed concurrently");
        assertThatThrownBy(() -> adapter.decide(7L, 10L, 9L, ApprovalStatus.APPROVED, "foreign"))
                .isInstanceOf(IllegalArgumentException.class).hasMessage("approval does not belong to tenant");
    }

    private ApprovalEntity approval(ApprovalStatus status, Instant expiresAt) {
        ApprovalEntity approval = new ApprovalEntity();
        approval.id = 10L;
        approval.tenantId = 7L;
        approval.actionType = "refund";
        approval.actionSummary = "refund order";
        approval.orderNo = "DEMO-001";
        approval.amount = new BigDecimal("88.00");
        approval.currency = "CNY";
        approval.eligibilityEvidence = "eligible=true; reason=within window";
        approval.status = status.name();
        approval.version = 0L;
        approval.expiresAt = expiresAt;
        return approval;
    }

    private ApprovalRequestDetails details() {
        return new ApprovalRequestDetails("DEMO-001", new BigDecimal("88.00"),
                "CNY", "eligible=true; reason=within window");
    }
}
