package com.lqq.supportflow.evaluation.domain;

import com.fasterxml.jackson.databind.annotation.JsonSerialize;
import com.fasterxml.jackson.databind.ser.std.ToStringSerializer;
import java.time.Instant;

public record EvaluationResult(
        @JsonSerialize(using = ToStringSerializer.class) Long id,
        @JsonSerialize(using = ToStringSerializer.class) Long caseId,
        String status,
        @JsonSerialize(using = ToStringSerializer.class) Long expectedDocumentId,
        Integer hitRank,
        Double topScore,
        Long latencyMs,
        String failureCode,
        Instant createdAt) { }
