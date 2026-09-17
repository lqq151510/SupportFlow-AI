package com.lqq.supportflow.evaluation.domain;

import com.fasterxml.jackson.databind.annotation.JsonSerialize;
import com.fasterxml.jackson.databind.ser.std.ToStringSerializer;
import java.time.Instant;

public record EvaluationRun(
        @JsonSerialize(using = ToStringSerializer.class) Long id,
        @JsonSerialize(using = ToStringSerializer.class) Long knowledgeBaseId,
        long knowledgeBaseVersion,
        String status,
        int totalCases,
        int evaluatedCases,
        int failedCases,
        Double recallAt1,
        Double recallAt3,
        Double recallAt6,
        Instant startedAt,
        Instant completedAt) { }
