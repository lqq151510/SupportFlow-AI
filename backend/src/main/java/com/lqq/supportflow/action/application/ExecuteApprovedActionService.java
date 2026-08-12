package com.lqq.supportflow.action.application;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.lqq.supportflow.action.domain.ActionExecutionPort;
import com.lqq.supportflow.eventing.EventConsumerService;
import com.lqq.supportflow.eventing.OutboxService;
import com.lqq.supportflow.eventing.PublishedOutboxEvent;
import java.util.LinkedHashMap;
import java.util.Map;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ExecuteApprovedActionService {
    private static final int SUPPORTED_SCHEMA_VERSION = 1;
    private static final String CONSUMER_NAME = "approved-action-executor";

    private final ActionExecutionPort executions;
    private final EventConsumerService consumers;
    private final OutboxService outbox;
    private final ObjectMapper json;

    public ExecuteApprovedActionService(ActionExecutionPort executions, EventConsumerService consumers,
                                        OutboxService outbox, ObjectMapper json) {
        this.executions = executions;
        this.consumers = consumers;
        this.outbox = outbox;
        this.json = json;
    }

    @EventListener
    @Transactional
    public void on(PublishedOutboxEvent event) throws Exception {
        if (!"approval.approved".equals(event.eventType())) return;

        JsonNode payload = json.readTree(event.payload());
        int schemaVersion = payload.path("schemaVersion").asInt(-1);
        if (schemaVersion != SUPPORTED_SCHEMA_VERSION) {
            throw new IllegalArgumentException("unsupported approval event schema version");
        }
        long approvalId = payload.path("approvalId").asLong(-1);
        long approvalVersion = payload.path("approvalVersion").asLong(-1);
        long executionVersion = payload.path("executionVersion").asLong(-1);
        String businessKey = requiredText(payload, "businessIdempotencyKey");
        String actionType = requiredText(payload, "actionType");
        if (approvalId <= 0 || approvalVersion <= 0 || executionVersion <= 0) {
            throw new IllegalArgumentException("approval event versions and id must be positive");
        }
        if (!"refund.request".equals(actionType) && !"compensation.issue".equals(actionType)) {
            throw new IllegalArgumentException("unsupported approved action type");
        }

        boolean executed = executions.executeOnce(
                event.tenantId(), approvalId, actionType, executionVersion, businessKey);
        if (executed) recordExecuted(event, payload, approvalId, approvalVersion, executionVersion, businessKey, actionType);

        // Mark consumption only after the business write and result event succeed. A thrown
        // exception leaves the ledger unclaimed so RocketMQ can retry or route to its DLQ.
        consumers.claim(event.tenantId(), CONSUMER_NAME, event.id());
    }

    private void recordExecuted(PublishedOutboxEvent event, JsonNode source, long approvalId,
                                long approvalVersion, long executionVersion,
                                String businessKey, String actionType) throws Exception {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("schemaVersion", SUPPORTED_SCHEMA_VERSION);
        payload.put("eventId", event.id().toString());
        payload.put("approvalId", Long.toString(approvalId));
        payload.put("approvalVersion", approvalVersion);
        payload.put("executionVersion", executionVersion);
        payload.put("businessIdempotencyKey", businessKey);
        payload.put("actionType", actionType);
        payload.put("orderNo", requiredText(source, "orderNo"));
        payload.put("amount", source.path("amount").decimalValue());
        payload.put("currency", requiredText(source, "currency"));
        String eventType = "refund.request".equals(actionType) ? "refund.executed" : "compensation.executed";
        outbox.record(event.tenantId(), eventType, "approval", Long.toString(approvalId),
                json.writeValueAsString(payload));
    }

    private String requiredText(JsonNode payload, String field) {
        String value = payload.path(field).asText();
        if (value.isBlank()) throw new IllegalArgumentException("approval event field is required: " + field);
        return value;
    }
}
