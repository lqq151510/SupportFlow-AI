package com.lqq.supportflow.model.infrastructure.protocol;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.lqq.supportflow.model.domain.ModelEvent;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Flux;

@Component
public class OpenAiCompatibleEventNormalizer {

    private final ObjectMapper json;

    public OpenAiCompatibleEventNormalizer(ObjectMapper json) { this.json = json; }

    public Flux<ModelEvent> normalize(Flux<String> dataFrames) {
        return Flux.defer(() -> {
            StreamState state = new StreamState();
            return dataFrames.concatMapIterable(frame -> toEvents(frame, state));
        });
    }

    private List<ModelEvent> toEvents(String frame, StreamState state) {
        if ("[DONE]".equals(frame)) {
            List<ModelEvent> events = new ArrayList<>();
            for (String callId : state.indexToId.values()) {
                if (state.completedCallIds.add(callId)) {
                    events.add(new ModelEvent.ToolCallCompleted(callId));
                }
            }
            events.add(new ModelEvent.ModelCompleted());
            return events;
        }
        try {
            JsonNode root = json.readTree(frame);
            List<ModelEvent> events = new ArrayList<>();
            JsonNode choice = root.path("choices").path(0);
            JsonNode delta = choice.path("delta");
            if (delta.hasNonNull("content")) events.add(new ModelEvent.TextDelta(delta.get("content").asText()));
            for (JsonNode tool : delta.path("tool_calls")) {
                int index = tool.path("index").asInt(0);
                String id = tool.path("id").asText();
                if (!id.isEmpty()) {
                    state.indexToId.put(index, id);
                } else {
                    id = state.indexToId.getOrDefault(index, "");
                }
                String name = tool.path("function").path("name").asText();
                if (!id.isEmpty() && !name.isEmpty()) events.add(new ModelEvent.ToolCallStarted(id, name));
                String arguments = tool.path("function").path("arguments").asText();
                if (!id.isEmpty() && !arguments.isEmpty()) events.add(new ModelEvent.ToolCallArgumentsDelta(id, arguments));
            }
            String finishReason = choice.path("finish_reason").asText();
            if ("tool_calls".equals(finishReason)) {
                for (String callId : state.indexToId.values()) {
                    if (state.completedCallIds.add(callId)) {
                        events.add(new ModelEvent.ToolCallCompleted(callId));
                    }
                }
            }
            JsonNode usage = root.path("usage");
            if (!usage.isMissingNode()) events.add(new ModelEvent.UsageReported(usage.path("prompt_tokens").asInt(), usage.path("completion_tokens").asInt()));
            return events;
        } catch (Exception exception) {
            return List.of(new ModelEvent.ModelFailed("PROTOCOL_ERROR", "invalid OpenAI-compatible event"));
        }
    }

    private static final class StreamState {
        private final Map<Integer, String> indexToId = new HashMap<>();
        private final Set<String> completedCallIds = new HashSet<>();
    }
}
