package com.lqq.supportflow.model;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.lqq.supportflow.model.domain.ChatModelGateway;
import com.lqq.supportflow.model.domain.ChatModelRequest;
import com.lqq.supportflow.model.domain.ModelEvent;
import java.util.List;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Flux;

@Service
public class ModelChatService {
    private final ChatModelGateway gateway;
    private final ObjectMapper json;

    public ModelChatService(ChatModelGateway gateway, ObjectMapper json) { this.gateway = gateway; this.json = json; }

    public Flux<ModelStreamEvent> stream(Long tenantId, List<ChatMessage> messages) {
        return gateway.stream(new ChatModelRequest(tenantId, messages.stream()
                        .map(message -> new ChatModelRequest.ChatMessage(message.role(), message.content())).toList()))
                .map(this::map).onErrorResume(exception -> Flux.just(new ModelStreamEvent("model.failed", "{\"code\":\"MODEL_UNAVAILABLE\"}")));
    }

    private ModelStreamEvent map(ModelEvent event) {
        try {
            return switch (event) {
                case ModelEvent.TextDelta text -> new ModelStreamEvent("text.delta", json.writeValueAsString(java.util.Map.of("text", text.text())));
                case ModelEvent.ToolCallStarted tool -> new ModelStreamEvent("tool.started", json.writeValueAsString(java.util.Map.of("callId", tool.callId(), "name", tool.name())));
                case ModelEvent.ToolCallArgumentsDelta tool -> new ModelStreamEvent("tool.arguments.delta", json.writeValueAsString(java.util.Map.of("callId", tool.callId(), "argumentsDelta", tool.argumentsDelta())));
                case ModelEvent.ToolCallCompleted tool -> new ModelStreamEvent("tool.completed", json.writeValueAsString(java.util.Map.of("callId", tool.callId())));
                case ModelEvent.UsageReported usage -> new ModelStreamEvent("usage.reported", json.writeValueAsString(java.util.Map.of("inputTokens", usage.inputTokens(), "outputTokens", usage.outputTokens())));
                case ModelEvent.ModelCompleted ignored -> new ModelStreamEvent("model.completed", "{}");
                case ModelEvent.ModelFailed failed -> new ModelStreamEvent("model.failed", json.writeValueAsString(java.util.Map.of("code", failed.code(), "message", failed.message())));
            };
        } catch (JsonProcessingException exception) { return new ModelStreamEvent("model.failed", "{\"code\":\"SERIALIZATION_ERROR\"}"); }
    }

    public record ChatMessage(String role, String content) { }
}
