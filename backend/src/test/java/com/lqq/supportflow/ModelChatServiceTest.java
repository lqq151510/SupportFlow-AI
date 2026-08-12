package com.lqq.supportflow;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.lqq.supportflow.model.ModelChatService;
import com.lqq.supportflow.model.ModelStreamEvent;
import com.lqq.supportflow.model.ModelTool;
import com.lqq.supportflow.model.domain.ChatModelGateway;
import com.lqq.supportflow.model.domain.ChatModelRequest;
import com.lqq.supportflow.model.domain.ModelEvent;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.mockito.Mockito;
import reactor.core.publisher.Flux;

class ModelChatServiceTest {

    @Test
    void mapsNormalizedModelEventsToThePublicConversationSafeContract() {
        ChatModelGateway gateway = Mockito.mock(ChatModelGateway.class);
        when(gateway.stream(any())).thenReturn(Flux.just(new ModelEvent.TextDelta("你好"), new ModelEvent.ModelCompleted()));

        List<ModelStreamEvent> events = new ModelChatService(gateway, new ObjectMapper())
                .stream(7L, List.of(new ModelChatService.ChatMessage("user", "你好"))).collectList().block();

        assertThat(events).containsExactly(new ModelStreamEvent("text.delta", "{\"text\":\"你好\"}"), new ModelStreamEvent("model.completed", "{}"));
    }

    @Test
    void mapsToolUsageAndFailureEventsAndForwardsToolDefinitions() throws Exception {
        ChatModelGateway gateway = Mockito.mock(ChatModelGateway.class);
        when(gateway.stream(any())).thenReturn(Flux.just(
                new ModelEvent.ToolCallStarted("call-1", "lookup_order"),
                new ModelEvent.ToolCallArgumentsDelta("call-1", "{\"orderNo\":"),
                new ModelEvent.ToolCallCompleted("call-1"),
                new ModelEvent.UsageReported(120, 24),
                new ModelEvent.ModelFailed("UPSTREAM_TIMEOUT", "provider timed out")));
        ObjectMapper json = new ObjectMapper();
        ModelTool tool = new ModelTool("lookup_order", "查询订单", Map.of("type", "object"));

        List<ModelStreamEvent> events = new ModelChatService(gateway, json)
                .stream(7L, List.of(new ModelChatService.ChatMessage("user", "查询订单")), List.of(tool))
                .collectList().block();

        assertThat(events).extracting(ModelStreamEvent::type).containsExactly(
                "tool.started", "tool.arguments.delta", "tool.completed", "usage.reported", "model.failed");
        assertThat(json.readTree(events.get(0).data())).isEqualTo(
                json.readTree("{\"callId\":\"call-1\",\"name\":\"lookup_order\"}"));
        assertThat(json.readTree(events.get(1).data())).isEqualTo(
                json.readTree("{\"callId\":\"call-1\",\"argumentsDelta\":\"{\\\"orderNo\\\":\"}"));
        assertThat(json.readTree(events.get(2).data())).isEqualTo(json.readTree("{\"callId\":\"call-1\"}"));
        assertThat(json.readTree(events.get(3).data())).isEqualTo(
                json.readTree("{\"inputTokens\":120,\"outputTokens\":24}"));
        assertThat(json.readTree(events.get(4).data())).isEqualTo(
                json.readTree("{\"code\":\"UPSTREAM_TIMEOUT\",\"message\":\"provider timed out\"}"));

        ArgumentCaptor<ChatModelRequest> request = ArgumentCaptor.forClass(ChatModelRequest.class);
        verify(gateway).stream(request.capture());
        assertThat(request.getValue()).isEqualTo(new ChatModelRequest(
                7L,
                List.of(new ChatModelRequest.ChatMessage("user", "查询订单")),
                List.of(new ChatModelRequest.ToolDefinition(
                        "lookup_order", "查询订单", Map.of("type", "object")))));
    }
}
