package com.lqq.supportflow.conversation.application;

import com.lqq.supportflow.conversation.GenerationRequestedEvent;
import com.lqq.supportflow.conversation.HandoffRequiredEvent;
import com.lqq.supportflow.conversation.domain.ConversationPort;
import com.lqq.supportflow.conversation.domain.Generation;
import com.lqq.supportflow.conversation.domain.GenerationEventStore;
import com.lqq.supportflow.conversation.domain.HandoffPolicy;
import com.lqq.supportflow.conversation.domain.MessageSubmission;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class SubmitCustomerMessageService {
    private final ConversationPort conversations;
    private final GenerationEventStore events;
    private final HandoffPolicy handoff;
    private final ApplicationEventPublisher publisher;

    public SubmitCustomerMessageService(ConversationPort conversations, GenerationEventStore events,
                                        HandoffPolicy handoff, ApplicationEventPublisher publisher) {
        this.conversations = conversations;
        this.events = events;
        this.handoff = handoff;
        this.publisher = publisher;
    }

    @Transactional
    public Generation submit(Long tenantId, Long customerId, Long conversationId,
                             String content, String idempotencyKey) {
        if (!conversations.belongsTo(tenantId, customerId, conversationId)) {
            throw new IllegalArgumentException("conversation does not belong to customer");
        }
        MessageSubmission submission = conversations.submit(
                tenantId, conversationId, content, idempotencyKey);
        if (!submission.newlyCreated()) return submission.generation();

        Generation generation = submission.generation();
        if (handoff.requiresHandoff(content)) {
            generation = conversations.requireHandoff(tenantId, conversationId, generation.id());
            events.appendIfAbsent(tenantId, generation.id(), "handoff.required",
                    "{\"status\":\"HANDOFF_REQUIRED\"}");
            publisher.publishEvent(new HandoffRequiredEvent(tenantId, customerId, conversationId,
                    generation.id(), "customer request requires an agent"));
            return generation;
        }
        events.appendIfAbsent(tenantId, generation.id(), "generation.queued", "{\"status\":\"QUEUED\"}");
        publisher.publishEvent(new GenerationRequestedEvent(
                tenantId, customerId, conversationId, generation.id(), content));
        return generation;
    }
}
