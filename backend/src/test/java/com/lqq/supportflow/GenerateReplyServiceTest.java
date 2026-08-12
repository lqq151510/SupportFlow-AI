package com.lqq.supportflow;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.when;

import com.lqq.supportflow.conversation.GenerationRequestedEvent;
import com.lqq.supportflow.conversation.application.GenerateReplyService;
import com.lqq.supportflow.conversation.application.GenerationLifecycleService;
import com.lqq.supportflow.conversation.domain.GenerationEventStore;
import com.lqq.supportflow.action.ToolExecutionService;
import com.lqq.supportflow.action.ToolExecutionResult;
import com.lqq.supportflow.knowledge.KnowledgeRetrievalService;
import com.lqq.supportflow.knowledge.RetrievedCitation;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.lqq.supportflow.model.ModelChatService;
import com.lqq.supportflow.model.ModelStreamEvent;
import org.junit.jupiter.api.Test;
import reactor.core.publisher.Flux;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.web.reactive.function.client.WebClientResponseException;

class GenerateReplyServiceTest {

    @Test
    void persistsEveryStreamDeltaAndCompletesTheGeneration() {
        GenerationLifecycleService lifecycle = mock(GenerationLifecycleService.class);
        GenerationEventStore events = mock(GenerationEventStore.class);
        ModelChatService models = mock(ModelChatService.class);
        KnowledgeRetrievalService knowledge = mock(KnowledgeRetrievalService.class);
        when(lifecycle.start(any())).thenReturn(true);
        when(knowledge.retrieve(1L, "订单到哪里了")).thenReturn(citations());
        when(models.stream(eq(1L), any(), any())).thenReturn(Flux.just(
                new ModelStreamEvent("text.delta", "{\"text\":\"您好\"}"),
                new ModelStreamEvent("text.delta", "{\"text\":\"，订单已发货\"}"),
                new ModelStreamEvent("usage.reported", "{\"inputTokens\":11,\"outputTokens\":22}"),
                new ModelStreamEvent("model.completed", "{}")));

        new GenerateReplyService(lifecycle, events, models, mock(ToolExecutionService.class), knowledge, new ObjectMapper())
                .generate(new GenerationRequestedEvent(1L, 4L, 2L, 3L, "订单到哪里了"));

        verify(events).append(1L, 3L, "text.delta", "{\"text\":\"您好\"}");
        verify(events).append(1L, 3L, "text.delta", "{\"text\":\"，订单已发货\"}");
        verify(lifecycle).complete(any(), eq("您好，订单已发货"), eq(11), eq(22), any(Long.class));
    }

    @Test
    void executesAHighRiskToolAsAnApprovalAndHandsTheConversationOff() {
        GenerationLifecycleService lifecycle = mock(GenerationLifecycleService.class);
        GenerationEventStore events = mock(GenerationEventStore.class);
        ModelChatService models = mock(ModelChatService.class);
        ToolExecutionService tools = mock(ToolExecutionService.class);
        KnowledgeRetrievalService knowledge = mock(KnowledgeRetrievalService.class);
        when(lifecycle.start(any())).thenReturn(true);
        when(knowledge.retrieve(1L, "我要退款")).thenReturn(citations());
        when(models.stream(eq(1L), any(), any())).thenReturn(Flux.just(
                new ModelStreamEvent("tool.started", "{\"callId\":\"call-1\",\"name\":\"refund.request\"}"),
                new ModelStreamEvent("tool.arguments.delta", "{\"callId\":\"call-1\",\"argumentsDelta\":\"{\\\"orderNo\\\":\\\"DEMO-001\\\"}\"}"),
                new ModelStreamEvent("tool.completed", "{\"callId\":\"call-1\"}"),
                new ModelStreamEvent("model.completed", "{}")));
        when(tools.execute(eq(1L), eq(4L), eq("refund.request"), any()))
                .thenReturn(new ToolExecutionResult("refund.request", "PENDING_APPROVAL", java.util.Map.of("approvalId", 9L)));

        new GenerateReplyService(lifecycle, events, models, tools, knowledge, new ObjectMapper())
                .generate(new GenerationRequestedEvent(1L, 4L, 2L, 3L, "我要退款"));

        verify(tools).execute(eq(1L), eq(4L), eq("refund.request"), eq(java.util.Map.of("orderNo", "DEMO-001")));
        verify(lifecycle).handoff(any(), eq("high-risk action requires approval"));
        verify(events).append(eq(1L), eq(3L), eq("tool.result"), any());
    }

    @Test
    void handsOffWithoutTenantKnowledgeInsteadOfGeneratingAnUnsupportedAnswer() {
        GenerationLifecycleService lifecycle = mock(GenerationLifecycleService.class);
        GenerationEventStore events = mock(GenerationEventStore.class);
        ModelChatService models = mock(ModelChatService.class);
        KnowledgeRetrievalService knowledge = mock(KnowledgeRetrievalService.class);
        when(lifecycle.start(any())).thenReturn(true);
        when(knowledge.retrieve(1L, "未知规则")).thenReturn(java.util.List.of());

        new GenerateReplyService(lifecycle, events, models, mock(ToolExecutionService.class), knowledge, new ObjectMapper())
                .generate(new GenerationRequestedEvent(1L, 4L, 2L, 3L, "未知规则"));

        verify(events).appendIfAbsent(1L, 3L, "knowledge.insufficient", "{\"reason\":\"NO_TENANT_EVIDENCE\"}");
        verify(lifecycle).handoff(any(), eq("knowledge evidence is insufficient"));
        verify(models, org.mockito.Mockito.never()).stream(any(), any(), any());
    }

    @Test
    void retriesOneServerFailureBeforeAnyToolExecutionAndResetsPartialOutput() {
        GenerationLifecycleService lifecycle = mock(GenerationLifecycleService.class);
        GenerationEventStore events = mock(GenerationEventStore.class);
        ModelChatService models = mock(ModelChatService.class);
        KnowledgeRetrievalService knowledge = mock(KnowledgeRetrievalService.class);
        when(lifecycle.start(any())).thenReturn(true);
        when(knowledge.retrieve(1L, "物流状态")).thenReturn(citations());
        WebClientResponseException unavailable = WebClientResponseException.create(
                HttpStatus.SERVICE_UNAVAILABLE.value(), "unavailable", HttpHeaders.EMPTY, new byte[0], null);
        when(models.stream(eq(1L), any(), any()))
                .thenReturn(Flux.concat(Flux.just(new ModelStreamEvent("text.delta", "{\"text\":\"旧\"}")), Flux.error(unavailable)))
                .thenReturn(Flux.just(new ModelStreamEvent("text.delta", "{\"text\":\"新答案\"}"), new ModelStreamEvent("model.completed", "{}")));

        new GenerateReplyService(lifecycle, events, models, mock(ToolExecutionService.class), knowledge, new ObjectMapper())
                .generate(new GenerationRequestedEvent(1L, 4L, 2L, 3L, "物流状态"));

        verify(models, times(2)).stream(eq(1L), any(), any());
        verify(events).append(1L, 3L, "generation.reset", "{\"reason\":\"MODEL_RETRY\"}");
        verify(lifecycle).complete(any(), eq("新答案"), eq(0), eq(0), any(Long.class));
    }

    private java.util.List<RetrievedCitation> citations() { return java.util.List.of(new RetrievedCitation(8L, 9L, 10L, "订单规则", 0.9, 1)); }
}
