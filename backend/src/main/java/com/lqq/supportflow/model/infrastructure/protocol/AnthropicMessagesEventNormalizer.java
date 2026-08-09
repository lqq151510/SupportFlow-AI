package com.lqq.supportflow.model.infrastructure.protocol;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.lqq.supportflow.model.domain.ModelEvent;
import java.util.ArrayList;
import java.util.List;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Flux;

@Component
public class AnthropicMessagesEventNormalizer {

    private final ObjectMapper json;

    public AnthropicMessagesEventNormalizer(ObjectMapper json) { this.json = json; }

    public Flux<ModelEvent> normalize(Flux<AnthropicSseFrame> frames) {
        return frames.concatMapIterable(this::toEvents);
    }

    private List<ModelEvent> toEvents(AnthropicSseFrame frame) {
        try {
            JsonNode root = json.readTree(frame.data());
            List<ModelEvent> events = new ArrayList<>();
            switch (frame.event()) {
                case "content_block_start" -> {
                    JsonNode block = root.path("content_block");
                    if ("tool_use".equals(block.path("type").asText())) {
                        events.add(new ModelEvent.ToolCallStarted(block.path("id").asText(), block.path("name").asText()));
                    }
                }
                case "content_block_delta" -> {
                    JsonNode delta = root.path("delta");
                    if (delta.hasNonNull("text")) events.add(new ModelEvent.TextDelta(delta.get("text").asText()));
                    if (delta.hasNonNull("partial_json")) events.add(new ModelEvent.ToolCallArgumentsDelta(root.path("index").asText(), delta.get("partial_json").asText()));
                }
                case "content_block_stop" -> events.add(new ModelEvent.ToolCallCompleted(root.path("index").asText()));
                case "message_delta" -> {
                    JsonNode usage = root.path("usage");
                    events.add(new ModelEvent.UsageReported(usage.path("input_tokens").asInt(), usage.path("output_tokens").asInt()));
                }
                case "message_stop" -> events.add(new ModelEvent.ModelCompleted());
                default -> { }
            }
            return events;
        } catch (Exception exception) {
            return List.of(new ModelEvent.ModelFailed("PROTOCOL_ERROR", "invalid Anthropic event"));
        }
    }

    public record AnthropicSseFrame(String event, String data) { }
}
