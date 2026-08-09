package com.lqq.supportflow.ticket.domain;
import java.util.List;
public interface TicketCommentPort { TicketComment add(Long tenantId,Long ticketId,Long authorMembershipId,String content); List<TicketComment> list(Long tenantId,Long ticketId); }
