package com.lqq.supportflow.conversation.infrastructure.persistence;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.UpdateWrapper;
import com.lqq.supportflow.conversation.domain.*;
import com.lqq.supportflow.shared.ConflictException;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import org.springframework.stereotype.Component;

@Component
public class MyBatisConversationAdapter implements ConversationPort {

    private final ConversationMapper conversations;
    private final ConversationMessageMapper messages;
    private final GenerationMapper generations;

    public MyBatisConversationAdapter(ConversationMapper conversations,
                                      ConversationMessageMapper messages,
                                      GenerationMapper generations) {
        this.conversations = conversations;
        this.messages = messages;
        this.generations = generations;
    }

    @Override
    public Conversation create(Long tenantId, Long customerId) {
        Instant now = Instant.now();
        ConversationEntity entity = new ConversationEntity();
        entity.tenantId = tenantId;
        entity.customerId = customerId;
        entity.status = ConversationStatus.AI_ACTIVE.name();
        entity.createdAt = now;
        entity.updatedAt = now;
        conversations.insert(entity);
        return new Conversation(entity.id, ConversationStatus.AI_ACTIVE);
    }

    @Override
    public boolean belongsTo(Long tenantId, Long customerId, Long conversationId) {
        return conversations.exists(new QueryWrapper<ConversationEntity>()
                .eq("id", conversationId)
                .eq("tenant_id", tenantId)
                .eq("customer_id", customerId));
    }

    @Override
    public boolean ownsGeneration(Long tenantId, Long customerId, Long generationId) {
        GenerationEntity generation = generations.selectOne(new QueryWrapper<GenerationEntity>()
                .eq("id", generationId)
                .eq("tenant_id", tenantId));
        return generation != null && belongsTo(tenantId, customerId, generation.conversationId);
    }

    @Override
    public MessageSubmission submit(Long tenantId, Long conversationId, String content, String idempotencyKey) {
        if (idempotencyKey == null || idempotencyKey.isBlank()) {
            throw new IllegalArgumentException("Idempotency-Key is required");
        }
        ConversationMessageEntity existing = messages.selectOne(new QueryWrapper<ConversationMessageEntity>()
                .eq("tenant_id", tenantId)
                .eq("conversation_id", conversationId)
                .eq("idempotency_key", idempotencyKey));
        if (existing != null) {
            if (!content.equals(existing.content)) {
                throw new ConflictException("Idempotency-Key was already used for a different message");
            }
            GenerationEntity generation = generations.selectById(existing.generationId);
            return new MessageSubmission(new Generation(generation.id, generation.conversationId, GenerationStatus.valueOf(generation.status)), false);
        }
        Instant now = Instant.now();
        ConversationMessageEntity message = new ConversationMessageEntity();
        message.tenantId = tenantId;
        message.conversationId = conversationId;
        message.senderType = "CUSTOMER";
        message.content = content;
        message.idempotencyKey = idempotencyKey;
        message.createdAt = now;
        messages.insert(message);

        GenerationEntity generation = new GenerationEntity();
        generation.tenantId = tenantId;
        generation.conversationId = conversationId;
        generation.userMessageId = message.id;
        generation.status = GenerationStatus.QUEUED.name();
        generation.createdAt = now;
        generation.updatedAt = now;
        generations.insert(generation);

        messages.update(new ConversationMessageEntity(), new UpdateWrapper<ConversationMessageEntity>()
                .eq("id", message.id)
                .set("generation_id", generation.id));
        return new MessageSubmission(new Generation(generation.id, conversationId, GenerationStatus.QUEUED), true);
    }

    @Override
    public boolean startGeneration(Long tenantId, Long conversationId, Long generationId) {
        return generations.update(new GenerationEntity(), new UpdateWrapper<GenerationEntity>()
                .eq("id", generationId)
                .eq("tenant_id", tenantId)
                .eq("conversation_id", conversationId)
                .eq("status", GenerationStatus.QUEUED.name())
                .set("status", GenerationStatus.RUNNING.name())
                .set("updated_at", Instant.now())) == 1;
    }

    @Override
    public Generation completeGeneration(Long tenantId, Long conversationId, Long generationId, String response, int inputTokens, int outputTokens, long latencyMs) {
        Instant now = Instant.now();
        int updated = generations.update(new GenerationEntity(), new UpdateWrapper<GenerationEntity>()
                .eq("id", generationId)
                .eq("tenant_id", tenantId)
                .eq("conversation_id", conversationId)
                .eq("status", GenerationStatus.RUNNING.name())
                .set("status", GenerationStatus.COMPLETED.name())
                .set("input_tokens", inputTokens)
                .set("output_tokens", outputTokens)
                .set("latency_ms", latencyMs)
                .set("updated_at", now));
        if (updated != 1) return current(tenantId, generationId);
        ConversationMessageEntity answer = new ConversationMessageEntity();
        answer.tenantId = tenantId;
        answer.conversationId = conversationId;
        answer.senderType = "AI";
        answer.content = response;
        answer.createdAt = now;
        messages.insert(answer);
        return new Generation(generationId, conversationId, GenerationStatus.COMPLETED);
    }

    @Override
    public Generation requireHandoff(Long tenantId, Long conversationId, Long generationId) {
        Instant now = Instant.now();
        int updated = generations.update(new GenerationEntity(), new UpdateWrapper<GenerationEntity>()
                .eq("id", generationId)
                .eq("tenant_id", tenantId)
                .eq("conversation_id", conversationId)
                .in("status", GenerationStatus.QUEUED.name(), GenerationStatus.RUNNING.name())
                .set("status", GenerationStatus.HANDOFF_REQUIRED.name())
                .set("updated_at", now));
        if (updated == 0) return current(tenantId, generationId);
        conversations.update(new ConversationEntity(), new UpdateWrapper<ConversationEntity>()
                .eq("id", conversationId)
                .eq("tenant_id", tenantId)
                .set("status", ConversationStatus.WAITING_AGENT.name())
                .set("updated_at", now));
        return new Generation(generationId, conversationId, GenerationStatus.HANDOFF_REQUIRED);
    }

    @Override
    public List<ConversationMessage> findRecentMessages(Long tenantId, Long conversationId, int limit) {
        List<ConversationMessageEntity> list = messages.selectList(
                new QueryWrapper<ConversationMessageEntity>()
                        .eq("tenant_id", tenantId)
                        .eq("conversation_id", conversationId)
                        .orderByDesc("created_at")
                        .last("LIMIT " + Math.max(1, limit))
        );
        if (list == null || list.isEmpty()) return List.of();
        List<ConversationMessageEntity> mutable = new ArrayList<>(list);
        Collections.reverse(mutable);
        return mutable.stream().map(m -> new ConversationMessage(m.senderType, m.content)).toList();
    }

    private Generation current(Long tenantId, Long generationId) {
        GenerationEntity existing = generations.selectOne(new QueryWrapper<GenerationEntity>()
                .eq("id", generationId)
                .eq("tenant_id", tenantId));
        if (existing == null) throw new IllegalArgumentException("generation does not belong to tenant");
        return new Generation(existing.id, existing.conversationId, GenerationStatus.valueOf(existing.status));
    }
}
