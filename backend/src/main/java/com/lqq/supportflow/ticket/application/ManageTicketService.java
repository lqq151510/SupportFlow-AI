package com.lqq.supportflow.ticket.application;

import com.lqq.supportflow.conversation.AgentConversationReplyService;
import com.lqq.supportflow.shared.AssignableMemberProvider;
import com.lqq.supportflow.ticket.domain.Ticket;
import com.lqq.supportflow.ticket.domain.TicketComment;
import com.lqq.supportflow.ticket.domain.TicketCommentPort;
import com.lqq.supportflow.ticket.domain.TicketPort;
import com.lqq.supportflow.ticket.domain.TicketStatus;
import java.util.List;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ManageTicketService {
    private final TicketPort tickets;
    private final TicketCommentPort comments;
    private final AssignableMemberProvider assignableMembers;
    private final AgentConversationReplyService replies;

    public ManageTicketService(TicketPort tickets, TicketCommentPort comments, AssignableMemberProvider assignableMembers,
            AgentConversationReplyService replies) {
        this.tickets = tickets;
        this.comments = comments;
        this.assignableMembers = assignableMembers;
        this.replies = replies;
    }

    public List<Ticket> list(Long tenantId) { return tickets.list(tenantId); }
    public Ticket get(Long tenantId, Long ticketId) { return tickets.get(tenantId, ticketId); }

    @Transactional
    public Ticket claim(Long tenantId, Long ticketId, Long membershipId, String idempotencyKey) {
        return tickets.claim(tenantId, ticketId, membershipId, idempotencyKey);
    }

    @Transactional
    public Ticket assign(Long tenantId, Long ticketId, Long targetMembershipId, Long assignedByMembershipId) {
        if (!assignableMembers.isAssignable(tenantId, targetMembershipId)) {
            throw new IllegalArgumentException("target member is not assignable in tenant");
        }
        return tickets.assign(tenantId, ticketId, targetMembershipId, assignedByMembershipId);
    }

    @Transactional
    public Ticket changeStatus(Long tenantId, Long ticketId, TicketStatus status) { return tickets.changeStatus(tenantId, ticketId, status); }

    @Transactional
    public TicketComment addComment(Long tenantId, Long ticketId, Long membershipId, String content) { return comments.add(tenantId, ticketId, membershipId, content); }

    public List<TicketComment> comments(Long tenantId, Long ticketId) { return comments.list(tenantId, ticketId); }

    @Transactional
    public AgentConversationReplyService.AgentReply reply(Long tenantId, Long ticketId, Long membershipId, String content,
            String idempotencyKey) {
        Ticket ticket = tickets.get(tenantId, ticketId);
        if (ticket.assignedMembershipId() == null || !ticket.assignedMembershipId().equals(membershipId)) {
            throw new IllegalArgumentException("ticket must be claimed by the replying agent");
        }
        if (ticket.status() == TicketStatus.CLOSED) throw new IllegalArgumentException("closed ticket cannot receive a reply");
        return replies.reply(tenantId, ticket.conversationId(), membershipId, content, idempotencyKey);
    }
}
