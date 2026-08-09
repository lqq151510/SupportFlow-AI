package com.lqq.supportflow.conversation.application;

import com.lqq.supportflow.conversation.GenerationRequestedEvent;
import com.lqq.supportflow.conversation.HandoffRequiredEvent;
import com.lqq.supportflow.conversation.domain.ConversationPort;
import com.lqq.supportflow.conversation.domain.GenerationEventStore;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

@Service
public class GenerationLifecycleService {
    private final ConversationPort conversations; private final GenerationEventStore events; private final ApplicationEventPublisher publisher;
    public GenerationLifecycleService(ConversationPort conversations, GenerationEventStore events, ApplicationEventPublisher publisher) { this.conversations = conversations; this.events = events; this.publisher = publisher; }

    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public boolean start(GenerationRequestedEvent request) {
        boolean started = conversations.startGeneration(request.tenantId(), request.conversationId(), request.generationId());
        if (started) events.appendIfAbsent(request.tenantId(), request.generationId(), "generation.running", "{\"status\":\"RUNNING\"}");
        return started;
    }

    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void complete(GenerationRequestedEvent request, String response, int inputTokens, int outputTokens, long latencyMs) {
        conversations.completeGeneration(request.tenantId(), request.conversationId(), request.generationId(), response, inputTokens, outputTokens, latencyMs);
    }

    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void handoff(GenerationRequestedEvent request, String reason) {
        conversations.requireHandoff(request.tenantId(), request.conversationId(), request.generationId());
        events.appendIfAbsent(request.tenantId(), request.generationId(), "handoff.required", "{\"status\":\"HANDOFF_REQUIRED\"}");
        publisher.publishEvent(new HandoffRequiredEvent(request.tenantId(), request.customerId(), request.conversationId(), request.generationId(), reason));
    }
}
