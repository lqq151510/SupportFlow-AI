package com.lqq.supportflow.model.infrastructure.protocol;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.lqq.supportflow.model.domain.ModelEvent;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Flux;

@Component
public class AnthropicMessagesEventNormalizer {

    private final ObjectMapper json;

    public AnthropicMessagesEventNormalizer(ObjectMapper json) { this.json = json; }

    public Flux<ModelEvent> normalize(Flux<AnthropicSseFrame> frames) {
        return Flux.defer(() -> {
            Map<String, String> indexToId = new HashMap<>();
            return frames.concatMapIterable(frame -> toEvents(frame, indexToId));
        });
    }

    private List<ModelEvent> toEvents(AnthropicSseFrame frame, Map<String, String> indexToId) {
        try {
            JsonNode root = json.readTree(frame.data());
            List<ModelEvent> events = new ArrayList<>();
            switch (frame.event()) {
                case "content_block_start" -> {
                    String index = root.path("index").asText();
                    JsonNode block = root.path("content_block");
                    if ("tool_use".equals(block.path("type").asText())) {
                        String id = block.path("id").asText();
                        if (!index.isEmpty() && !id.isEmpty()) {
                            indexToId.put(index, id);
                        }
                        events.add(new ModelEvent.ToolCallStarted(id, block.path("name").asText()));
                    }
                }
                case "content_block_delta" -> {
                    JsonNode delta = root.path("delta");
                    if (delta.hasNonNull("text")) events.add(new ModelEvent.TextDelta(delta.get("text").asText()));
                    if (delta.hasNonNull("partial_json")) {
                        String index = root.path("index").asText();
                        String callId = indexToId.getOrDefault(index, index);
                        events.add(new ModelEvent.ToolCallArgumentsDelta(callId, delta.get("partial_json").asText()));
                    }
                }
                case "content_block_stop" -> {
                    String index = root.path("index").asText();
                    String callId = indexToId.getOrDefault(index, index);
                    events.add(new ModelEvent.ToolCallCompleted(callId));
                }
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
