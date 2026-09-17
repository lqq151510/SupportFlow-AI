package com.lqq.supportflow.evaluation.api;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

public record CreateEvaluationCaseRequest(
        @NotBlank @Size(max = 2000) String question,
        @NotNull Long expectedDocumentId,
        @Size(max = 80) String category) { }
