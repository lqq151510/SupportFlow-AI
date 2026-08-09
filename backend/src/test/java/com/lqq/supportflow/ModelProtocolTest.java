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
}
