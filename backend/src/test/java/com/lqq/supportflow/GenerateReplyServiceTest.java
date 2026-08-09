package com.lqq.supportflow;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.lqq.supportflow.conversation.GenerationRequestedEvent;
import com.lqq.supportflow.conversation.application.GenerateReplyService;
import com.lqq.supportflow.conversation.application.GenerationLifecycleService;
import com.lqq.supportflow.conversation.domain.GenerationEventStore;
import com.lqq.supportflow.model.ModelChatService;
import com.lqq.supportflow.model.ModelStreamEvent;
import org.junit.jupiter.api.Test;
import reactor.core.publisher.Flux;

class GenerateReplyServiceTest {

    @Test
    void persistsEveryStreamDeltaAndCompletesTheGeneration() {
        GenerationLifecycleService lifecycle = mock(GenerationLifecycleService.class);
        GenerationEventStore events = mock(GenerationEventStore.class);
        ModelChatService models = mock(ModelChatService.class);
        when(lifecycle.start(any())).thenReturn(true);
        when(models.stream(eq(1L), any())).thenReturn(Flux.just(
                new ModelStreamEvent("text.delta", "{\"text\":\"您好\"}"),
                new ModelStreamEvent("text.delta", "{\"text\":\"，订单已发货\"}"),
                new ModelStreamEvent("model.completed", "{}")));

        new GenerateReplyService(lifecycle, events, models)
                .generate(new GenerationRequestedEvent(1L, 4L, 2L, 3L, "订单到哪里了"));

        verify(events).append(3L, "text.delta", "{\"text\":\"您好\"}");
        verify(events).append(3L, "text.delta", "{\"text\":\"，订单已发货\"}");
        verify(lifecycle).complete(any(), eq("您好，订单已发货"));
    }
}
