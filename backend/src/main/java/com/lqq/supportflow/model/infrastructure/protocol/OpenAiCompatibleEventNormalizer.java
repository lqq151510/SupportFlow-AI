package com.lqq.supportflow.model.infrastructure.protocol;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.lqq.supportflow.model.domain.ModelEvent;
import java.util.ArrayList;
import java.util.List;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Flux;

@Component
public class OpenAiCompatibleEventNormalizer {

    private final ObjectMapper json;

    public OpenAiCompatibleEventNormalizer(ObjectMapper json) { this.json = json; }

    public Flux<ModelEvent> normalize(Flux<String> dataFrames) {
        return dataFrames.concatMapIterable(this::toEvents);
    }

    private List<ModelEvent> toEvents(String frame) {
        if ("[DONE]".equals(frame)) return List.of(new ModelEvent.ModelCompleted());
        try {
            JsonNode root = json.readTree(frame);
            List<ModelEvent> events = new ArrayList<>();
            JsonNode choice = root.path("choices").path(0);
            JsonNode delta = choice.path("delta");
            if (delta.hasNonNull("content")) events.add(new ModelEvent.TextDelta(delta.get("content").asText()));
            for (JsonNode tool : delta.path("tool_calls")) {
                String id = tool.path("id").asText();
                String name = tool.path("function").path("name").asText();
                if (!id.isEmpty() && !name.isEmpty()) events.add(new ModelEvent.ToolCallStarted(id, name));
                String arguments = tool.path("function").path("arguments").asText();
                if (!id.isEmpty() && !arguments.isEmpty()) events.add(new ModelEvent.ToolCallArgumentsDelta(id, arguments));
            }
            JsonNode usage = root.path("usage");
            if (!usage.isMissingNode()) events.add(new ModelEvent.UsageReported(usage.path("prompt_tokens").asInt(), usage.path("completion_tokens").asInt()));
            return events;
        } catch (Exception exception) {
            return List.of(new ModelEvent.ModelFailed("PROTOCOL_ERROR", "invalid OpenAI-compatible event"));
        }
    }
}
