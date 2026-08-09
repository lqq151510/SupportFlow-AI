package com.lqq.supportflow.ticket.api;
import com.lqq.supportflow.ticket.domain.TicketStatus; import jakarta.validation.constraints.NotNull;
public record ChangeTicketStatusRequest(@NotNull TicketStatus status) { }
