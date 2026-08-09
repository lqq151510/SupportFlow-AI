package com.lqq.supportflow.ticket.domain;
public interface TicketPort { Ticket create(Long tenantId,Long customerId,Long conversationId,String title,TicketPriority priority); java.util.List<Ticket> list(Long tenantId); Ticket claim(Long tenantId,Long ticketId,Long membershipId); Ticket changeStatus(Long tenantId,Long ticketId,TicketStatus target); }
