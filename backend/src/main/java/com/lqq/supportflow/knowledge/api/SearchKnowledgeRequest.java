package com.lqq.supportflow.knowledge.api;
import jakarta.validation.constraints.NotBlank;
public record SearchKnowledgeRequest(@NotBlank String query) { }
