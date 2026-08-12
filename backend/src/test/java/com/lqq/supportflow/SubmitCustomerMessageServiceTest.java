package com.lqq.supportflow;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.lqq.supportflow.conversation.GenerationRequestedEvent;
import com.lqq.supportflow.conversation.application.SubmitCustomerMessageService;
import com.lqq.supportflow.conversation.domain.ConversationPort;
import com.lqq.supportflow.conversation.domain.Generation;
import com.lqq.supportflow.conversation.domain.GenerationEventStore;
import com.lqq.supportflow.conversation.domain.GenerationStatus;
import com.lqq.supportflow.conversation.domain.HandoffPolicy;
import com.lqq.supportflow.conversation.domain.MessageSubmission;
import org.junit.jupiter.api.Test;
import org.springframework.context.ApplicationEventPublisher;

class SubmitCustomerMessageServiceTest {
    @Test
    void anIdempotentReplayDoesNotPublishTheGenerationRequestAgain() {
        ConversationPort conversations = mock(ConversationPort.class);
        GenerationEventStore events = mock(GenerationEventStore.class);
        HandoffPolicy handoff = mock(HandoffPolicy.class);
        ApplicationEventPublisher publisher = mock(ApplicationEventPublisher.class);
        Generation generation = new Generation(3L, 2L, GenerationStatus.RUNNING);
        when(conversations.belongsTo(1L, 4L, 2L)).thenReturn(true);
        when(conversations.submit(1L, 2L, "hello", "message-1"))
                .thenReturn(new MessageSubmission(generation, false));
        SubmitCustomerMessageService service = new SubmitCustomerMessageService(
                conversations, events, handoff, publisher);

        assertThat(service.submit(1L, 4L, 2L, "hello", "message-1")).isEqualTo(generation);

        verify(events, never()).appendIfAbsent(1L, 3L, "generation.queued", "{\"status\":\"QUEUED\"}");
        verify(publisher, never()).publishEvent(org.mockito.ArgumentMatchers.any(GenerationRequestedEvent.class));
    }
}
