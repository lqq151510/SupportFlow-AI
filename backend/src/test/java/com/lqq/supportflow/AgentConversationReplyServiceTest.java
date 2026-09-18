package com.lqq.supportflow;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.lqq.supportflow.conversation.AgentConversationReplyService;
import com.lqq.supportflow.conversation.infrastructure.persistence.ConversationMessageEntity;
import com.lqq.supportflow.conversation.infrastructure.persistence.ConversationMessageMapper;
import org.junit.jupiter.api.Test;

class AgentConversationReplyServiceTest {

    @Test
    void writesAnAgentReplyAndReplaysTheSameIdempotencyKey() {
        ConversationMessageMapper messages = mock(ConversationMessageMapper.class);
        ConversationMessageEntity existing = new ConversationMessageEntity();
        existing.id = 11L;
        existing.conversationId = 8L;
        existing.senderType = "AGENT";
        existing.content = "已为您处理";
        when(messages.selectOne(any())).thenReturn(null, existing);
        AgentConversationReplyService service = new AgentConversationReplyService(messages);

        assertThat(service.reply(7L, 8L, 9L, "已为您处理", "reply-1").content()).isEqualTo("已为您处理");
        assertThat(service.reply(7L, 8L, 9L, "已为您处理", "reply-1").id()).isEqualTo(11L);
        verify(messages).insert(any(ConversationMessageEntity.class));
    }

    @Test
    void rejectsMissingOrConflictingIdempotencyKeys() {
        ConversationMessageMapper messages = mock(ConversationMessageMapper.class);
        ConversationMessageEntity existing = new ConversationMessageEntity();
        existing.senderType = "CUSTOMER";
        existing.content = "旧消息";
        when(messages.selectOne(any())).thenReturn(existing);
        AgentConversationReplyService service = new AgentConversationReplyService(messages);

        assertThatThrownBy(() -> service.reply(7L, 8L, 9L, "回复", " "))
                .isInstanceOf(IllegalArgumentException.class).hasMessage("Idempotency-Key is required");
        assertThatThrownBy(() -> service.reply(7L, 8L, 9L, "回复", "reply-1"))
                .isInstanceOf(com.lqq.supportflow.shared.ConflictException.class)
                .hasMessage("Idempotency-Key was already used for a different message");
    }

    @Test
    void rejectsNullKeysAndKeysOwnedByNonAgentMessagesEvenWhenTheContentMatches() {
        ConversationMessageMapper messages = mock(ConversationMessageMapper.class);
        ConversationMessageEntity existing = new ConversationMessageEntity();
        existing.senderType = "CUSTOMER";
        existing.content = "回复";
        when(messages.selectOne(any())).thenReturn(existing);
        AgentConversationReplyService service = new AgentConversationReplyService(messages);

        assertThatThrownBy(() -> service.reply(7L, 8L, 9L, "回复", null))
                .isInstanceOf(IllegalArgumentException.class).hasMessage("Idempotency-Key is required");
        assertThatThrownBy(() -> service.reply(7L, 8L, 9L, "回复", "reply-1"))
                .isInstanceOf(com.lqq.supportflow.shared.ConflictException.class)
                .hasMessage("Idempotency-Key was already used for a different message");
    }
}
