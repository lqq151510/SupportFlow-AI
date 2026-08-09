package com.lqq.supportflow.ticket.domain;

import com.fasterxml.jackson.databind.annotation.JsonSerialize;
import com.fasterxml.jackson.databind.ser.std.ToStringSerializer;
import java.time.Instant;

public record Ticket(
        @JsonSerialize(using = ToStringSerializer.class) Long id,
        @JsonSerialize(using = ToStringSerializer.class) Long customerId,
        String title,
        TicketStatus status,
        TicketPriority priority,
        @JsonSerialize(using = ToStringSerializer.class) Long assignedMembershipId,
        Instant firstResponseDueAt,
        Instant resolutionDueAt) { }
