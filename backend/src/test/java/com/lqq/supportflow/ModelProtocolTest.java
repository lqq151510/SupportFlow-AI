package com.lqq.supportflow;

import static org.assertj.core.api.Assertions.assertThat;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.lqq.supportflow.model.domain.ModelEvent;
import com.lqq.supportflow.model.infrastructure.protocol.AnthropicMessagesEventNormalizer;
import com.lqq.supportflow.model.infrastructure.protocol.OpenAiCompatibleEventNormalizer;
import java.util.List;
import org.junit.jupiter.api.Test;
import reactor.core.publisher.Flux;

class ModelProtocolTest {

    private final ObjectMapper json = new ObjectMapper();

    @Test
    void normalizesOpenAiTextToolsUsageAndCompletion() {
        var normalizer = new OpenAiCompatibleEventNormalizer(json);
        List<ModelEvent> events = normalizer.normalize(Flux.just(
                        "{\"choices\":[{\"delta\":{\"content\":\"你好\"}}]}",
                        "{\"choices\":[{\"delta\":{\"tool_calls\":[{\"id\":\"call-1\",\"function\":{\"name\":\"order.lookup\",\"arguments\":\"{\\\"orderNo\\\":\\\"A1\\\"}\"}}]}}]}",
                        "{\"usage\":{\"prompt_tokens\":12,\"completion_tokens\":7}}",
                        "[DONE]"))
                .collectList().block();
        assertThat(events).contains(new ModelEvent.TextDelta("你好"), new ModelEvent.ToolCallStarted("call-1", "order.lookup"),
                new ModelEvent.UsageReported(12, 7), new ModelEvent.ModelCompleted());
    }

    @Test
    void normalizesAnthropicTextToolUsageAndCompletion() {
        var normalizer = new AnthropicMessagesEventNormalizer(json);
        List<ModelEvent> events = normalizer.normalize(Flux.just(
                        new AnthropicMessagesEventNormalizer.AnthropicSseFrame("content_block_start", "{\"content_block\":{\"type\":\"tool_use\",\"id\":\"tool-1\",\"name\":\"shipment.track\"}}"),
                        new AnthropicMessagesEventNormalizer.AnthropicSseFrame("content_block_delta", "{\"index\":0,\"delta\":{\"text\":\"正在查询\"}}"),
                        new AnthropicMessagesEventNormalizer.AnthropicSseFrame("message_delta", "{\"usage\":{\"input_tokens\":9,\"output_tokens\":5}}"),
                        new AnthropicMessagesEventNormalizer.AnthropicSseFrame("message_stop", "{}")))
                .collectList().block();
        assertThat(events).contains(new ModelEvent.ToolCallStarted("tool-1", "shipment.track"), new ModelEvent.TextDelta("正在查询"),
                new ModelEvent.UsageReported(9, 5), new ModelEvent.ModelCompleted());
    }

    @Test
    void normalizesOpenAiArgumentDeltasCompletionAndProtocolErrors() {
        var normalizer = new OpenAiCompatibleEventNormalizer(json);

        List<ModelEvent> events = normalizer.normalize(Flux.just(
                        "{\"choices\":[{\"delta\":{\"tool_calls\":[{\"id\":\"tool-1\",\"function\":{\"name\":\"refund.check\",\"arguments\":\"{\\\"orderNo\\\":\\\"DEMO-001\\\"}\"}}]}}]}",
                        "{not-json}",
                        "[DONE]"))
                .collectList().block();

        assertThat(events).containsExactly(
                new ModelEvent.ToolCallStarted("tool-1", "refund.check"),
                new ModelEvent.ToolCallArgumentsDelta("tool-1", "{\"orderNo\":\"DEMO-001\"}"),
                new ModelEvent.ModelFailed("PROTOCOL_ERROR", "invalid OpenAI-compatible event"),
                new ModelEvent.ToolCallCompleted("tool-1"),
                new ModelEvent.ModelCompleted());
    }

    @Test
    void normalizesOpenAiMultiChunkStreamingToolCallsWithoutIdInSubsequentChunks() {
        var normalizer = new OpenAiCompatibleEventNormalizer(json);
        List<ModelEvent> events = normalizer.normalize(Flux.just(
                        "{\"choices\":[{\"delta\":{\"tool_calls\":[{\"index\":0,\"id\":\"call-abc\",\"function\":{\"name\":\"order.lookup\",\"arguments\":\"\"}}]}}]}",
                        "{\"choices\":[{\"delta\":{\"tool_calls\":[{\"index\":0,\"function\":{\"arguments\":\"{\\\"orderNo\\\":\\\"\"}}]}}]}",
                        "{\"choices\":[{\"delta\":{\"tool_calls\":[{\"index\":0,\"function\":{\"arguments\":\"SO-123\\\"}\"}}]}}]}",
                        "{\"choices\":[{\"finish_reason\":\"tool_calls\"}]}",
                        "[DONE]"))
                .collectList().block();

        assertThat(events).containsExactly(
                new ModelEvent.ToolCallStarted("call-abc", "order.lookup"),
                new ModelEvent.ToolCallArgumentsDelta("call-abc", "{\"orderNo\":\""),
                new ModelEvent.ToolCallArgumentsDelta("call-abc", "SO-123\"}"),
                new ModelEvent.ToolCallCompleted("call-abc"),
                new ModelEvent.ModelCompleted());
    }

    @Test
    void normalizesAnthropicToolUseWithMappedIndexToCallId() {
        var normalizer = new AnthropicMessagesEventNormalizer(json);
        List<ModelEvent> events = normalizer.normalize(Flux.just(
                        new AnthropicMessagesEventNormalizer.AnthropicSseFrame("content_block_start", "{\"index\":0,\"content_block\":{\"type\":\"tool_use\",\"id\":\"toolu_123\",\"name\":\"order.lookup\"}}"),
                        new AnthropicMessagesEventNormalizer.AnthropicSseFrame("content_block_delta", "{\"index\":0,\"delta\":{\"type\":\"input_json_delta\",\"partial_json\":\"{\\\"orderNo\\\":\\\"SO-123\\\"}\"}}"),
                        new AnthropicMessagesEventNormalizer.AnthropicSseFrame("content_block_stop", "{\"index\":0}"),
                        new AnthropicMessagesEventNormalizer.AnthropicSseFrame("message_stop", "{}")))
                .collectList().block();

        assertThat(events).containsExactly(
                new ModelEvent.ToolCallStarted("toolu_123", "order.lookup"),
                new ModelEvent.ToolCallArgumentsDelta("toolu_123", "{\"orderNo\":\"SO-123\"}"),
                new ModelEvent.ToolCallCompleted("toolu_123"),
                new ModelEvent.ModelCompleted());
    }

    @Test
    void normalizesAnthropicArgumentsStopUnknownAndProtocolErrors() {
        var normalizer = new AnthropicMessagesEventNormalizer(json);

        List<ModelEvent> events = normalizer.normalize(Flux.just(
                        new AnthropicMessagesEventNormalizer.AnthropicSseFrame("content_block_delta", "{\"index\":2,\"delta\":{\"partial_json\":\"{\\\"orderNo\\\":\\\"DEMO-001\\\"}\"}}"),
                        new AnthropicMessagesEventNormalizer.AnthropicSseFrame("content_block_stop", "{\"index\":2}"),
                        new AnthropicMessagesEventNormalizer.AnthropicSseFrame("ping", "{}"),
                        new AnthropicMessagesEventNormalizer.AnthropicSseFrame("message_delta", "not-json")))
                .collectList().block();

        assertThat(events).containsExactly(
                new ModelEvent.ToolCallArgumentsDelta("2", "{\"orderNo\":\"DEMO-001\"}"),
                new ModelEvent.ToolCallCompleted("2"),
                new ModelEvent.ModelFailed("PROTOCOL_ERROR", "invalid Anthropic event"));
    }
}
