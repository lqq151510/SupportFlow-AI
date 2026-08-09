package com.lqq.supportflow;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.lqq.supportflow.model.ModelChatService;
import com.lqq.supportflow.model.ModelStreamEvent;
import com.lqq.supportflow.model.domain.ChatModelGateway;
import com.lqq.supportflow.model.domain.ModelEvent;
import java.util.List;
import org.junit.jupiter.api.Test;
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
}
