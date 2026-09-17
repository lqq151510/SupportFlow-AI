package com.lqq.supportflow.evaluation.domain;

import com.fasterxml.jackson.databind.annotation.JsonSerialize;
import com.fasterxml.jackson.databind.ser.std.ToStringSerializer;
import java.time.Instant;

public record EvaluationCase(
        @JsonSerialize(using = ToStringSerializer.class) Long id,
        @JsonSerialize(using = ToStringSerializer.class) Long knowledgeBaseId,
        String question,
        @JsonSerialize(using = ToStringSerializer.class) Long expectedDocumentId,
        String category,
        boolean enabled,
        Instant createdAt) { }
