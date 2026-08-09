package com.lqq.supportflow.conversation.api;
import jakarta.validation.constraints.NotBlank;
public record SubmitMessageRequest(@NotBlank String content) { }
