package com.lqq.supportflow;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.mockito.ArgumentMatchers.eq;

import com.lqq.supportflow.action.ToolExecutionResult;
import com.lqq.supportflow.action.ToolExecutionService;
import com.lqq.supportflow.action.application.ManageApprovalService;
import com.lqq.supportflow.action.domain.Approval;
import com.lqq.supportflow.action.domain.ApprovalStatus;
import com.lqq.supportflow.action.domain.ApprovalRequestDetails;
import com.lqq.supportflow.commerce.CommerceSupportToolService;
import com.lqq.supportflow.commerce.CommerceToolResult;
import java.time.Instant;
import java.math.BigDecimal;
import java.util.Map;
import org.junit.jupiter.api.Test;

class ToolExecutionServiceTest {
    @Test
    void executesReadOnlyCommerceToolsWithoutCreatingAnApproval() {
        CommerceSupportToolService commerce = mock(CommerceSupportToolService.class);
        ManageApprovalService approvals = mock(ManageApprovalService.class);
        when(commerce.shipmentTrack(1L, 2L, "DEMO-001")).thenReturn(new CommerceToolResult("shipment.track", Map.of("status", "IN_TRANSIT")));
        ToolExecutionResult result = new ToolExecutionService(commerce, approvals).execute(1L, 2L, "shipment.track", Map.of("orderNo", "DEMO-001"));
        assertThat(result.status()).isEqualTo("COMPLETED");
        assertThat(result.data()).containsEntry("status", "IN_TRANSIT");
    }

    @Test
    void turnsHighRiskToolsIntoApprovalRequests() {
        CommerceSupportToolService commerce = mock(CommerceSupportToolService.class);
        ManageApprovalService approvals = mock(ManageApprovalService.class);
        when(commerce.orderLookup(1L, 2L, "DEMO-001")).thenReturn(new CommerceToolResult(
                "order.lookup", Map.of("totalAmount", new BigDecimal("88.00"), "currency", "CNY")));
        when(commerce.refundEligibility(1L, 2L, "DEMO-001")).thenReturn(new CommerceToolResult(
                "refund.checkEligibility", Map.of("eligible", true, "reason", "within window")));
        when(approvals.create(any(), any(), any(), any(), any(ApprovalRequestDetails.class), any()))
                .thenReturn(new Approval(9L, "refund.request", "refund", "DEMO-001",
                        new BigDecimal("88.00"), "CNY", "eligible=true; reason=within window",
                        null, null, 0, ApprovalStatus.PENDING, Instant.now()));
        ToolExecutionResult result = new ToolExecutionService(commerce, approvals).execute(1L, 2L, "refund.request", Map.of("orderNo", "DEMO-001"));
        assertThat(result.status()).isEqualTo("PENDING_APPROVAL");
        assertThat(result.data()).containsEntry("approvalId", 9L);
        verify(approvals).create(eq(1L), eq(2L), eq("refund.request"),
                eq("refund.request for order DEMO-001"),
                eq(new ApprovalRequestDetails("DEMO-001", new BigDecimal("88.00"), "CNY",
                        "eligible=true; reason=within window")), eq(null));
    }
}
