package com.lqq.supportflow.evaluation.domain;

import java.util.List;
import java.util.Optional;

public interface EvaluationPort {
    EvaluationCase createCase(Long tenantId, Long knowledgeBaseId, String question, Long expectedDocumentId, String category);
    List<EvaluationCase> listCases(Long tenantId, Long knowledgeBaseId);
    void deleteCase(Long tenantId, Long knowledgeBaseId, Long caseId);
    EvaluationRun createRun(Long tenantId, Long knowledgeBaseId, long knowledgeBaseVersion, int totalCases);
    void saveResult(Long tenantId, Long runId, Long caseId, Long expectedDocumentId, Integer hitRank, Double topScore, long latencyMs);
    void saveFailedResult(Long tenantId, Long runId, Long caseId, Long expectedDocumentId, long latencyMs, String failureCode);
    void completeRun(Long tenantId, Long runId, int evaluatedCases, int failedCases, Double recallAt1, Double recallAt3, Double recallAt6);
    Optional<EvaluationRun> findRun(Long tenantId, Long runId);
    List<EvaluationRun> listRuns(Long tenantId, Long knowledgeBaseId);
    List<EvaluationResult> listResults(Long tenantId, Long runId);
}
