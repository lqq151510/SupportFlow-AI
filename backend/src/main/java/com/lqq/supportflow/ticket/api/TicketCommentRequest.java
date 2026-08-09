package com.lqq.supportflow.ticket.api;
import jakarta.validation.constraints.NotBlank;
public record TicketCommentRequest(@NotBlank String content) { }
