package com.lqq.supportflow.ticket.domain;
import java.time.Instant;
public record TicketComment(Long id,Long ticketId,Long authorMembershipId,String content,Instant createdAt) { }
