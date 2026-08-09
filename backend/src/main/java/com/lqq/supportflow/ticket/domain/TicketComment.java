package com.lqq.supportflow.ticket.domain;

import com.fasterxml.jackson.databind.annotation.JsonSerialize;
import com.fasterxml.jackson.databind.ser.std.ToStringSerializer;
import java.time.Instant;

public record TicketComment(
        @JsonSerialize(using = ToStringSerializer.class) Long id,
        @JsonSerialize(using = ToStringSerializer.class) Long ticketId,
        @JsonSerialize(using = ToStringSerializer.class) Long authorMembershipId,
        String content,
        Instant createdAt) { }
