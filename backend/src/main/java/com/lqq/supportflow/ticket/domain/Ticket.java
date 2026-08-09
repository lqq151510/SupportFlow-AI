package com.lqq.supportflow.ticket.domain;
import java.time.Instant;
public record Ticket(Long id,TicketStatus status,TicketPriority priority,Long assignedMembershipId,Instant firstResponseDueAt,Instant resolutionDueAt) { }
