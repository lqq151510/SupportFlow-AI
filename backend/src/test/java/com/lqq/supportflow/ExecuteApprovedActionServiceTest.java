package com.lqq.supportflow;

import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.inOrder;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.lqq.supportflow.action.application.ExecuteApprovedActionService;
import com.lqq.supportflow.action.domain.ActionExecutionPort;
import com.lqq.supportflow.eventing.EventConsumerService;
import com.lqq.supportflow.eventing.OutboxService;
import com.lqq.supportflow.eventing.PublishedOutboxEvent;
import org.junit.jupiter.api.Test;
import org.mockito.InOrder;

class ExecuteApprovedActionServiceTest {
    private static final String PAYLOAD = """
            {"schemaVersion":1,"approvalId":"91","approvalVersion":1,"executionVersion":1,
             "businessIdempotencyKey":"approval:91:v1:execution:1","actionType":"refund.request",
             "orderNo":"DEMO-001","amount":88.00,"currency":"CNY"}
            """;

    @Test
    void recordsTheResultBeforeClaimingTheConsumedEvent() throws Exception {
        ActionExecutionPort executions = mock(ActionExecutionPort.class);
        EventConsumerService consumers = mock(EventConsumerService.class);
        OutboxService outbox = mock(OutboxService.class);
        when(executions.executeOnce(7L, 91L, "refund.request", 1,
                "approval:91:v1:execution:1")).thenReturn(true);
        ExecuteApprovedActionService service = new ExecuteApprovedActionService(
                executions, consumers, outbox, new ObjectMapper());

        service.on(new PublishedOutboxEvent(41L, 7L, "approval.approved", PAYLOAD));

        InOrder order = inOrder(executions, outbox, consumers);
        order.verify(executions).executeOnce(7L, 91L, "refund.request", 1,
                "approval:91:v1:execution:1");
        order.verify(outbox).record(eq(7L), eq("refund.executed"), eq("approval"),
                eq("91"), anyString());
        order.verify(consumers).claim(7L, "approved-action-executor", 41L);
    }

    @Test
    void leavesTheEventUnclaimedWhenBusinessExecutionFails() {
        ActionExecutionPort executions = mock(ActionExecutionPort.class);
        EventConsumerService consumers = mock(EventConsumerService.class);
        OutboxService outbox = mock(OutboxService.class);
        when(executions.executeOnce(7L, 91L, "refund.request", 1,
                "approval:91:v1:execution:1")).thenThrow(new IllegalStateException("temporary failure"));
        ExecuteApprovedActionService service = new ExecuteApprovedActionService(
                executions, consumers, outbox, new ObjectMapper());

        assertThatThrownBy(() -> service.on(
                new PublishedOutboxEvent(41L, 7L, "approval.approved", PAYLOAD)))
                .isInstanceOf(IllegalStateException.class).hasMessage("temporary failure");

        verify(consumers, never()).claim(7L, "approved-action-executor", 41L);
        verify(outbox, never()).record(eq(7L), eq("refund.executed"), eq("approval"),
                eq("91"), anyString());
    }

    @Test
    void rejectsUnknownEventSchemaWithoutClaimingIt() {
        ActionExecutionPort executions = mock(ActionExecutionPort.class);
        EventConsumerService consumers = mock(EventConsumerService.class);
        OutboxService outbox = mock(OutboxService.class);
        ExecuteApprovedActionService service = new ExecuteApprovedActionService(
                executions, consumers, outbox, new ObjectMapper());

        assertThatThrownBy(() -> service.on(new PublishedOutboxEvent(
                41L, 7L, "approval.approved", "{\"schemaVersion\":2}")))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("unsupported approval event schema version");
        verify(consumers, never()).claim(7L, "approved-action-executor", 41L);
    }
}
