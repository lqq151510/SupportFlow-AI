package com.lqq.supportflow.conversation.application;

import com.lqq.supportflow.conversation.GenerationRequestedEvent;
import com.lqq.supportflow.conversation.HandoffRequiredEvent;
import com.lqq.supportflow.conversation.domain.ConversationPort;
import com.lqq.supportflow.conversation.domain.GenerationEventStore;
import com.lqq.supportflow.model.ModelChatService;
import com.lqq.supportflow.model.ModelStreamEvent;
import com.lqq.supportflow.shared.AuthenticatedPrincipal;
import com.lqq.supportflow.shared.TenantContext;
import java.util.List;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.event.TransactionalEventListener;

@Service
public class GenerateReplyService {
    private final ConversationPort conversations; private final GenerationEventStore events; private final ModelChatService models; private final ApplicationEventPublisher publisher;
    public GenerateReplyService(ConversationPort conversations, GenerationEventStore events, ModelChatService models, ApplicationEventPublisher publisher) { this.conversations = conversations; this.events = events; this.models = models; this.publisher = publisher; }

    @Async("generationExecutor")
    @TransactionalEventListener
    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void generate(GenerationRequestedEvent request) {
        TenantContext.set(new AuthenticatedPrincipal(request.customerId(), request.tenantId(), 0L, "CUSTOMER"));
        try {
            if (!conversations.startGeneration(request.tenantId(), request.conversationId(), request.generationId())) return;
            events.appendIfAbsent(request.generationId(), "generation.running", "{\"status\":\"RUNNING\"}");
            StringBuilder response = new StringBuilder(); boolean failed = false;
            for (ModelStreamEvent event : models.stream(request.tenantId(), List.of(new ModelChatService.ChatMessage("user", request.content()))).toIterable()) {
                events.append(request.generationId(), event.type(), event.data());
                if ("text.delta".equals(event.type())) response.append(extractText(event.data()));
                if ("model.failed".equals(event.type())) failed = true;
            }
            if (failed) handoff(request, "model generation failed"); else conversations.completeGeneration(request.tenantId(), request.conversationId(), request.generationId(), response.toString());
        } catch (Exception exception) { handoff(request, "model generation failed"); } finally { TenantContext.clear(); }
    }

    private void handoff(GenerationRequestedEvent request, String reason) { conversations.requireHandoff(request.tenantId(), request.conversationId(), request.generationId()); events.appendIfAbsent(request.generationId(), "handoff.required", "{\"status\":\"HANDOFF_REQUIRED\"}"); publisher.publishEvent(new HandoffRequiredEvent(request.tenantId(), request.customerId(), request.conversationId(), request.generationId(), reason)); }
    private String extractText(String data) { int start = data.indexOf("\"text\":\""); if(start < 0) return ""; int content = start + 8; int end = data.lastIndexOf('"'); return end > content ? data.substring(content, end).replace("\\\"", "\"").replace("\\n", "\n") : ""; }
}
