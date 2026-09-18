package com.lqq.supportflow.conversation;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.lqq.supportflow.conversation.infrastructure.persistence.ConversationMessageEntity;
import com.lqq.supportflow.conversation.infrastructure.persistence.ConversationMessageMapper;
import com.lqq.supportflow.shared.ConflictException;
import java.time.Instant;
import org.springframework.stereotype.Service;

/** Public application boundary for an agent's customer-visible message. */
@Service
public class AgentConversationReplyService {
    private final ConversationMessageMapper messages;

    public AgentConversationReplyService(ConversationMessageMapper messages) { this.messages = messages; }

    public AgentReply reply(Long tenantId, Long conversationId, Long membershipId, String content, String idempotencyKey) {
        if (idempotencyKey == null || idempotencyKey.isBlank()) throw new IllegalArgumentException("Idempotency-Key is required");
        ConversationMessageEntity existing = messages.selectOne(new QueryWrapper<ConversationMessageEntity>()
                .eq("tenant_id", tenantId).eq("conversation_id", conversationId).eq("idempotency_key", idempotencyKey));
        if (existing != null) {
            if (!content.equals(existing.content) || !"AGENT".equals(existing.senderType)) {
                throw new ConflictException("Idempotency-Key was already used for a different message");
            }
            return reply(existing);
        }
        ConversationMessageEntity message = new ConversationMessageEntity();
        message.tenantId = tenantId;
        message.conversationId = conversationId;
        message.senderType = "AGENT";
        message.content = content;
        message.idempotencyKey = idempotencyKey;
        message.createdAt = Instant.now();
        messages.insert(message);
        return reply(message);
    }

    private AgentReply reply(ConversationMessageEntity message) {
        return new AgentReply(message.id, message.conversationId, message.content, message.createdAt);
    }

    public record AgentReply(Long id, Long conversationId, String content, Instant createdAt) { }
}
