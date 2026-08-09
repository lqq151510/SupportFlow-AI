package com.lqq.supportflow.knowledge.api; import jakarta.validation.constraints.NotBlank;
public record RegisterKnowledgeDocumentRequest(@NotBlank String fileName,@NotBlank String content) { }
