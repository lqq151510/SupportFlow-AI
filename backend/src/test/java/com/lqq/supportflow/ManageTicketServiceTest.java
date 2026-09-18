package com.lqq.supportflow;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import com.lqq.supportflow.conversation.AgentConversationReplyService;
import com.lqq.supportflow.shared.AssignableMemberProvider;
import com.lqq.supportflow.ticket.application.ManageTicketService;
import com.lqq.supportflow.ticket.domain.Ticket;
import com.lqq.supportflow.ticket.domain.TicketCommentPort;
import com.lqq.supportflow.ticket.domain.TicketPort;
import com.lqq.supportflow.ticket.domain.TicketPriority;
import com.lqq.supportflow.ticket.domain.TicketStatus;
import java.time.Instant;
import org.junit.jupiter.api.Test;

class ManageTicketServiceTest {

    @Test
    void sendsTheReplyThroughTheTicketConversationForTheAssignedAgent() {
        TicketPort tickets = mock(TicketPort.class);
        AgentConversationReplyService replies = mock(AgentConversationReplyService.class);
        Ticket ticket = ticket(TicketStatus.OPEN, 9L);
        when(tickets.get(7L, 11L)).thenReturn(ticket);
        var expected = new AgentConversationReplyService.AgentReply(12L, 10L, "已处理", Instant.now());
        when(replies.reply(7L, 10L, 9L, "已处理", "reply-1")).thenReturn(expected);
        ManageTicketService service = service(tickets, replies);

        assertThat(service.reply(7L, 11L, 9L, "已处理", "reply-1")).isSameAs(expected);
        verify(replies).reply(7L, 10L, 9L, "已处理", "reply-1");
    }

    @Test
    void rejectsRepliesWhenTheTicketHasNotBeenClaimed() {
        TicketPort tickets = mock(TicketPort.class);
        AgentConversationReplyService replies = mock(AgentConversationReplyService.class);
        when(tickets.get(7L, 11L)).thenReturn(ticket(TicketStatus.OPEN, null));

        assertThatThrownBy(() -> service(tickets, replies).reply(7L, 11L, 9L, "已处理", "reply-1"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("ticket must be claimed by the replying agent");
        verifyNoInteractions(replies);
    }

    @Test
    void rejectsRepliesFromAnAgentOtherThanTheAssignee() {
        TicketPort tickets = mock(TicketPort.class);
        AgentConversationReplyService replies = mock(AgentConversationReplyService.class);
        when(tickets.get(7L, 11L)).thenReturn(ticket(TicketStatus.OPEN, 10L));

        assertThatThrownBy(() -> service(tickets, replies).reply(7L, 11L, 9L, "已处理", "reply-1"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("ticket must be claimed by the replying agent");
        verifyNoInteractions(replies);
    }

    @Test
    void rejectsRepliesToClosedTickets() {
        TicketPort tickets = mock(TicketPort.class);
        AgentConversationReplyService replies = mock(AgentConversationReplyService.class);
        when(tickets.get(7L, 11L)).thenReturn(ticket(TicketStatus.CLOSED, 9L));

        assertThatThrownBy(() -> service(tickets, replies).reply(7L, 11L, 9L, "已处理", "reply-1"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("closed ticket cannot receive a reply");
        verifyNoInteractions(replies);
    }

    private ManageTicketService service(TicketPort tickets, AgentConversationReplyService replies) {
        return new ManageTicketService(tickets, mock(TicketCommentPort.class), mock(AssignableMemberProvider.class), replies);
    }

    private Ticket ticket(TicketStatus status, Long assignedMembershipId) {
        Instant now = Instant.now();
        return new Ticket(11L, 8L, 10L, "订单咨询", status, TicketPriority.NORMAL, assignedMembershipId, now, now);
    }
}
