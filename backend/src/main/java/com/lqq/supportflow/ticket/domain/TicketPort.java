package com.lqq.supportflow.ticket.domain;
public interface TicketPort { Ticket create(Long tenantId,Long customerId,Long conversationId,String title,TicketPriority priority); }
