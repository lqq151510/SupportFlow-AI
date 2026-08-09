package com.lqq.supportflow.action;

import com.lqq.supportflow.action.application.ManageApprovalService;
import com.lqq.supportflow.action.domain.Approval;
import com.lqq.supportflow.commerce.CommerceSupportToolService;
import com.lqq.supportflow.commerce.CommerceToolResult;
import java.util.Map;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ToolExecutionService {
    private final CommerceSupportToolService commerce; private final ManageApprovalService approvals;
    public ToolExecutionService(CommerceSupportToolService commerce, ManageApprovalService approvals) { this.commerce = commerce; this.approvals = approvals; }

    @Transactional
    public ToolExecutionResult execute(Long tenantId, Long customerId, String toolName, Map<String, Object> arguments) {
        String orderNo = stringArgument(arguments, "orderNo");
        return switch (toolName) {
            case "order.lookup" -> completed(commerce.orderLookup(tenantId, customerId, orderNo));
            case "shipment.track" -> completed(commerce.shipmentTrack(tenantId, customerId, orderNo));
            case "refund.checkEligibility" -> completed(commerce.refundEligibility(tenantId, customerId, orderNo));
            case "refund.request", "compensation.issue" -> pendingApproval(tenantId, customerId, toolName, orderNo);
            default -> throw new IllegalArgumentException("unsupported support tool");
        };
    }

    private ToolExecutionResult completed(CommerceToolResult result) { return new ToolExecutionResult(result.toolName(), "COMPLETED", result.data()); }
    private ToolExecutionResult pendingApproval(Long tenantId, Long customerId, String toolName, String orderNo) { Approval approval = approvals.create(tenantId, customerId, toolName, toolName + " for order " + orderNo, null); return new ToolExecutionResult(toolName, "PENDING_APPROVAL", Map.of("approvalId", approval.id(), "orderNo", orderNo)); }
    private String stringArgument(Map<String, Object> arguments, String name) { Object value = arguments.get(name); if (!(value instanceof String text) || text.isBlank()) throw new IllegalArgumentException("tool argument " + name + " is required"); return text; }
}
