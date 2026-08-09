package com.lqq.supportflow.conversation.application;

import com.lqq.supportflow.conversation.GenerationRequestedEvent;
import com.lqq.supportflow.conversation.domain.GenerationEventStore;
import com.lqq.supportflow.model.ModelChatService;
import com.lqq.supportflow.model.ModelStreamEvent;
import com.lqq.supportflow.shared.AuthenticatedPrincipal;
import com.lqq.supportflow.shared.TenantContext;
import java.util.List;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.transaction.event.TransactionalEventListener;

@Service
public class GenerateReplyService {
    private final GenerationLifecycleService lifecycle; private final GenerationEventStore events; private final ModelChatService models;
    public GenerateReplyService(GenerationLifecycleService lifecycle, GenerationEventStore events, ModelChatService models) { this.lifecycle = lifecycle; this.events = events; this.models = models; }

    @Async("generationExecutor")
    @TransactionalEventListener
    public void generate(GenerationRequestedEvent request) {
        TenantContext.set(new AuthenticatedPrincipal(request.customerId(), request.tenantId(), 0L, "CUSTOMER"));
        try {
            if (!lifecycle.start(request)) return;
            StringBuilder response = new StringBuilder(); boolean failed = false;
            for (ModelStreamEvent event : models.stream(request.tenantId(), List.of(new ModelChatService.ChatMessage("user", request.content()))).toIterable()) {
                events.append(request.generationId(), event.type(), event.data());
                if ("text.delta".equals(event.type())) response.append(extractText(event.data()));
                if ("model.failed".equals(event.type())) failed = true;
            }
            if (failed) lifecycle.handoff(request, "model generation failed"); else lifecycle.complete(request, response.toString());
        } catch (Exception exception) { lifecycle.handoff(request, "model generation failed"); } finally { TenantContext.clear(); }
    }

    private String extractText(String data) { int start = data.indexOf("\"text\":\""); if(start < 0) return ""; int content = start + 8; int end = data.lastIndexOf('"'); return end > content ? data.substring(content, end).replace("\\\"", "\"").replace("\\n", "\n") : ""; }
}
