package com.lqq.supportflow.ticket.domain;
import java.time.Instant;
public record Ticket(Long id,TicketStatus status,TicketPriority priority,Instant firstResponseDueAt,Instant resolutionDueAt) { }
