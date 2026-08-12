package com.lqq.supportflow;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.lqq.supportflow.conversation.domain.ConversationStatus;
import com.lqq.supportflow.conversation.domain.GenerationStatus;
import com.lqq.supportflow.conversation.infrastructure.persistence.ConversationEntity;
import com.lqq.supportflow.conversation.infrastructure.persistence.ConversationMapper;
import com.lqq.supportflow.conversation.infrastructure.persistence.ConversationMessageEntity;
import com.lqq.supportflow.conversation.infrastructure.persistence.ConversationMessageMapper;
import com.lqq.supportflow.conversation.infrastructure.persistence.GenerationEntity;
import com.lqq.supportflow.conversation.infrastructure.persistence.GenerationMapper;
import com.lqq.supportflow.conversation.infrastructure.persistence.MyBatisConversationAdapter;
import org.junit.jupiter.api.Test;

class MyBatisConversationAdapterTest {

    @Test
    void createsConversationsAndChecksCustomerOwnership() {
        ConversationMapper conversations = mock(ConversationMapper.class);
        ConversationMessageMapper messages = mock(ConversationMessageMapper.class);
        GenerationMapper generations = mock(GenerationMapper.class);
        when(conversations.exists(any())).thenReturn(true, false);
        MyBatisConversationAdapter adapter = adapter(conversations, messages, generations);

        var created = adapter.create(7L, 8L);
        assertThat(created.status()).isEqualTo(ConversationStatus.AI_ACTIVE);
        assertThat(adapter.belongsTo(7L, 8L, 10L)).isTrue();
        assertThat(adapter.belongsTo(7L, 8L, 11L)).isFalse();
        verify(conversations).insert(any(ConversationEntity.class));
    }

    @Test
    void supportsIdempotentSubmissionAndGenerationOwnership() {
        ConversationMapper conversations = mock(ConversationMapper.class);
        ConversationMessageMapper messages = mock(ConversationMessageMapper.class);
        GenerationMapper generations = mock(GenerationMapper.class);
        ConversationMessageEntity existing = new ConversationMessageEntity();
        existing.generationId = 20L;
        existing.content = "hello";
        GenerationEntity generation = generation(20L, 10L, GenerationStatus.RUNNING);
        when(messages.selectOne(any())).thenReturn(existing);
        when(generations.selectById(20L)).thenReturn(generation);
        when(generations.selectOne(any())).thenReturn(generation, (GenerationEntity) null);
        when(conversations.exists(any())).thenReturn(true);
        MyBatisConversationAdapter adapter = adapter(conversations, messages, generations);

        assertThat(adapter.submit(7L, 10L, "hello", "idem").generation().status()).isEqualTo(GenerationStatus.RUNNING);
        assertThat(adapter.submit(7L, 10L, "hello", "idem").newlyCreated()).isFalse();
        assertThatThrownBy(() -> adapter.submit(7L, 10L, "different", "idem"))
                .isInstanceOf(com.lqq.supportflow.shared.ConflictException.class)
                .hasMessage("Idempotency-Key was already used for a different message");
        assertThat(adapter.ownsGeneration(7L, 8L, 20L)).isTrue();
        assertThat(adapter.ownsGeneration(7L, 8L, 21L)).isFalse();
    }

    @Test
    void createsNewSubmissionStartsAndCompletesGeneration() {
        ConversationMapper conversations = mock(ConversationMapper.class);
        ConversationMessageMapper messages = mock(ConversationMessageMapper.class);
        GenerationMapper generations = mock(GenerationMapper.class);
        when(messages.selectOne(any())).thenReturn(null);
        when(generations.update(any(), any())).thenReturn(1);
        MyBatisConversationAdapter adapter = adapter(conversations, messages, generations);

        assertThat(adapter.submit(7L, 10L, "hello", "idem").generation().status()).isEqualTo(GenerationStatus.QUEUED);
        assertThat(adapter.startGeneration(7L, 10L, 20L)).isTrue();
        assertThat(adapter.completeGeneration(7L, 10L, 20L, "answer", 5, 7, 23).status()).isEqualTo(GenerationStatus.COMPLETED);
        org.mockito.Mockito.verify(messages, org.mockito.Mockito.times(2)).insert(any(ConversationMessageEntity.class));
    }

    @Test
    void returnsCurrentGenerationOnConflictsAndRequiresTenantOwnership() {
        ConversationMapper conversations = mock(ConversationMapper.class);
        ConversationMessageMapper messages = mock(ConversationMessageMapper.class);
        GenerationMapper generations = mock(GenerationMapper.class);
        GenerationEntity completed = generation(20L, 10L, GenerationStatus.COMPLETED);
        when(generations.update(any(), any())).thenReturn(0, 1, 0);
        when(generations.selectOne(any())).thenReturn(completed, completed, null);
        MyBatisConversationAdapter adapter = adapter(conversations, messages, generations);

        assertThat(adapter.completeGeneration(7L, 10L, 20L, "answer", 5, 7, 23).status()).isEqualTo(GenerationStatus.COMPLETED);
        assertThat(adapter.requireHandoff(7L, 10L, 20L).status()).isEqualTo(GenerationStatus.HANDOFF_REQUIRED);
        assertThat(adapter.requireHandoff(7L, 10L, 20L).status()).isEqualTo(GenerationStatus.COMPLETED);
        assertThatThrownBy(() -> adapter.completeGeneration(7L, 10L, 20L, "answer", 5, 7, 23))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("generation does not belong to tenant");
    }

    private MyBatisConversationAdapter adapter(ConversationMapper conversations, ConversationMessageMapper messages, GenerationMapper generations) {
        return new MyBatisConversationAdapter(conversations, messages, generations);
    }

    private GenerationEntity generation(Long id, Long conversationId, GenerationStatus status) {
        GenerationEntity generation = new GenerationEntity();
        generation.id = id;
        generation.tenantId = 7L;
        generation.conversationId = conversationId;
        generation.status = status.name();
        return generation;
    }
}
