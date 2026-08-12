package com.lqq.supportflow.ticket.api;

import jakarta.validation.constraints.NotNull;

public record AssignTicketRequest(@NotNull Long membershipId) { }
