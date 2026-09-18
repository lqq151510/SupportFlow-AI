package com.lqq.supportflow.ticket.api;

import jakarta.validation.constraints.NotBlank;

public record AgentReplyRequest(@NotBlank String content) { }
