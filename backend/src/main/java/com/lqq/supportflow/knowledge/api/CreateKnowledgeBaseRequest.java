package com.lqq.supportflow.knowledge.api; import jakarta.validation.constraints.NotBlank;
public record CreateKnowledgeBaseRequest(@NotBlank String name,String description) { }
