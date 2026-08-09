package com.lqq.supportflow;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.lqq.supportflow.conversation.GenerationRequestedEvent;
import com.lqq.supportflow.conversation.application.GenerateReplyService;
import com.lqq.supportflow.conversation.application.GenerationLifecycleService;
import com.lqq.supportflow.conversation.domain.GenerationEventStore;
import com.lqq.supportflow.action.ToolExecutionService;
import com.lqq.supportflow.action.ToolExecutionResult;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.lqq.supportflow.model.ModelChatService;
import com.lqq.supportflow.model.ModelStreamEvent;
import org.junit.jupiter.api.Test;
import reactor.core.publisher.Flux;

class GenerateReplyServiceTest {

    @Test
    void persistsEveryStreamDeltaAndCompletesTheGeneration() {
        GenerationLifecycleService lifecycle = mock(GenerationLifecycleService.class);
        GenerationEventStore events = mock(GenerationEventStore.class);
        ModelChatService models = mock(ModelChatService.class);
        when(lifecycle.start(any())).thenReturn(true);
        when(models.stream(eq(1L), any(), any())).thenReturn(Flux.just(
                new ModelStreamEvent("text.delta", "{\"text\":\"您好\"}"),
                new ModelStreamEvent("text.delta", "{\"text\":\"，订单已发货\"}"),
                new ModelStreamEvent("model.completed", "{}")));

        new GenerateReplyService(lifecycle, events, models, mock(ToolExecutionService.class), new ObjectMapper())
                .generate(new GenerationRequestedEvent(1L, 4L, 2L, 3L, "订单到哪里了"));

        verify(events).append(1L, 3L, "text.delta", "{\"text\":\"您好\"}");
        verify(events).append(1L, 3L, "text.delta", "{\"text\":\"，订单已发货\"}");
        verify(lifecycle).complete(any(), eq("您好，订单已发货"));
    }

    @Test
    void executesAHighRiskToolAsAnApprovalAndHandsTheConversationOff() {
        GenerationLifecycleService lifecycle = mock(GenerationLifecycleService.class);
        GenerationEventStore events = mock(GenerationEventStore.class);
        ModelChatService models = mock(ModelChatService.class);
        ToolExecutionService tools = mock(ToolExecutionService.class);
        when(lifecycle.start(any())).thenReturn(true);
        when(models.stream(eq(1L), any(), any())).thenReturn(Flux.just(
                new ModelStreamEvent("tool.started", "{\"callId\":\"call-1\",\"name\":\"refund.request\"}"),
                new ModelStreamEvent("tool.arguments.delta", "{\"callId\":\"call-1\",\"argumentsDelta\":\"{\\\"orderNo\\\":\\\"DEMO-001\\\"}\"}"),
                new ModelStreamEvent("tool.completed", "{\"callId\":\"call-1\"}"),
                new ModelStreamEvent("model.completed", "{}")));
        when(tools.execute(eq(1L), eq(4L), eq("refund.request"), any()))
                .thenReturn(new ToolExecutionResult("refund.request", "PENDING_APPROVAL", java.util.Map.of("approvalId", 9L)));

        new GenerateReplyService(lifecycle, events, models, tools, new ObjectMapper())
                .generate(new GenerationRequestedEvent(1L, 4L, 2L, 3L, "我要退款"));

        verify(tools).execute(eq(1L), eq(4L), eq("refund.request"), eq(java.util.Map.of("orderNo", "DEMO-001")));
        verify(lifecycle).handoff(any(), eq("high-risk action requires approval"));
        verify(events).append(eq(1L), eq(3L), eq("tool.result"), any());
    }
}
