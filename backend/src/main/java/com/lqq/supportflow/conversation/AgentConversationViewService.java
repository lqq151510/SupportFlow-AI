package com.lqq.supportflow.conversation;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.lqq.supportflow.conversation.domain.GenerationEventStore;
import com.lqq.supportflow.conversation.infrastructure.persistence.ConversationMessageEntity;
import com.lqq.supportflow.conversation.infrastructure.persistence.ConversationMessageMapper;
import com.lqq.supportflow.conversation.infrastructure.persistence.GenerationEntity;
import com.lqq.supportflow.conversation.infrastructure.persistence.GenerationMapper;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import org.springframework.stereotype.Service;

@Service
public class AgentConversationViewService {
    private final ConversationMessageMapper messages;
    private final GenerationMapper generations;
    private final GenerationEventStore events;

    public AgentConversationViewService(ConversationMessageMapper messages, GenerationMapper generations, GenerationEventStore events) {
        this.messages = messages; this.generations = generations; this.events = events;
    }

    public ConversationView get(Long tenantId, Long conversationId) {
        List<MessageView> messageViews = messages.selectList(new QueryWrapper<ConversationMessageEntity>()
                        .eq("tenant_id", tenantId).eq("conversation_id", conversationId).orderByAsc("created_at"))
                .stream().map(message -> new MessageView(message.senderType, message.content, message.createdAt)).toList();
        List<TraceView> traces = new ArrayList<>();
        for (GenerationEntity generation : generations.selectList(new QueryWrapper<GenerationEntity>()
                .eq("tenant_id", tenantId).eq("conversation_id", conversationId).orderByAsc("created_at"))) {
            events.readAfter(tenantId, generation.id, null).stream()
                    .filter(event -> event.type().startsWith("knowledge.") || event.type().startsWith("tool."))
                    .map(event -> new TraceView(generation.id.toString(), event.type(), event.data()))
                    .forEach(traces::add);
        }
        return new ConversationView(messageViews, traces);
    }

    public record ConversationView(List<MessageView> messages, List<TraceView> traces) { }
    public record MessageView(String senderType, String content, Instant createdAt) { }
    public record TraceView(String generationId, String type, String data) { }
}
