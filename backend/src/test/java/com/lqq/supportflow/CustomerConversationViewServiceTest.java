package com.lqq.supportflow;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.lqq.supportflow.conversation.AgentConversationViewService;
import com.lqq.supportflow.conversation.CustomerConversationViewService;
import com.lqq.supportflow.conversation.domain.ConversationPort;
import java.time.Instant;
import java.util.List;
import org.junit.jupiter.api.Test;

class CustomerConversationViewServiceTest {

    @Test
    void returnsMessagesWithoutInternalTracesForTheOwningCustomer() {
        ConversationPort conversations = mock(ConversationPort.class);
        AgentConversationViewService views = mock(AgentConversationViewService.class);
        when(conversations.belongsTo(7L, 8L, 9L)).thenReturn(true);
        when(views.get(7L, 9L)).thenReturn(new AgentConversationViewService.ConversationView(
                List.of(new AgentConversationViewService.MessageView("AGENT", "您好", Instant.now())),
                List.of(new AgentConversationViewService.TraceView("10", "tool.called", "private"))));

        var result = new CustomerConversationViewService(conversations, views).get(7L, 8L, 9L);

        assertThat(result.messages()).hasSize(1);
        assertThat(result.traces()).isEmpty();
        verify(views).get(7L, 9L);
    }

    @Test
    void rejectsConversationsOutsideTheCustomerScope() {
        ConversationPort conversations = mock(ConversationPort.class);
        when(conversations.belongsTo(7L, 8L, 9L)).thenReturn(false);

        assertThatThrownBy(() -> new CustomerConversationViewService(conversations,
                mock(AgentConversationViewService.class)).get(7L, 8L, 9L))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("conversation does not belong to customer");
    }
}
