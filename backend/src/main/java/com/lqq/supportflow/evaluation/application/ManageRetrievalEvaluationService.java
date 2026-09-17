package com.lqq.supportflow.evaluation.application;

import com.lqq.supportflow.evaluation.domain.EvaluationCase;
import com.lqq.supportflow.evaluation.domain.EvaluationPort;
import com.lqq.supportflow.evaluation.domain.EvaluationResult;
import com.lqq.supportflow.evaluation.domain.EvaluationRun;
import com.lqq.supportflow.evaluation.domain.EvaluationRunDetails;
import com.lqq.supportflow.knowledge.KnowledgeEvaluationAccess;
import java.util.List;
import org.springframework.stereotype.Service;

@Service
public class ManageRetrievalEvaluationService {
    private final EvaluationPort evaluations;
    private final KnowledgeEvaluationAccess knowledge;

    public ManageRetrievalEvaluationService(EvaluationPort evaluations, KnowledgeEvaluationAccess knowledge) {
        this.evaluations = evaluations;
        this.knowledge = knowledge;
    }

    public EvaluationCase createCase(Long tenantId, Long knowledgeBaseId, String question, Long expectedDocumentId, String category) {
        knowledge.context(tenantId, knowledgeBaseId);
        knowledge.requireDocument(tenantId, knowledgeBaseId, expectedDocumentId);
        String normalizedQuestion = question == null ? "" : question.trim();
        if (normalizedQuestion.isEmpty()) throw new IllegalArgumentException("evaluation question is required");
        String normalizedCategory = category == null || category.isBlank() ? "GENERAL" : category.trim().toUpperCase();
        return evaluations.createCase(tenantId, knowledgeBaseId, normalizedQuestion, expectedDocumentId, normalizedCategory);
    }

    public List<EvaluationCase> listCases(Long tenantId, Long knowledgeBaseId) { knowledge.context(tenantId, knowledgeBaseId); return evaluations.listCases(tenantId, knowledgeBaseId); }
    public void deleteCase(Long tenantId, Long knowledgeBaseId, Long caseId) { knowledge.context(tenantId, knowledgeBaseId); evaluations.deleteCase(tenantId, knowledgeBaseId, caseId); }
    public List<EvaluationRun> listRuns(Long tenantId, Long knowledgeBaseId) { knowledge.context(tenantId, knowledgeBaseId); return evaluations.listRuns(tenantId, knowledgeBaseId); }
    public EvaluationRunDetails getRun(Long tenantId, Long runId) { EvaluationRun run = evaluations.findRun(tenantId, runId).orElseThrow(() -> new IllegalArgumentException("evaluation run does not belong to tenant")); return new EvaluationRunDetails(run, evaluations.listResults(tenantId, runId)); }

    public EvaluationRunDetails run(Long tenantId, Long knowledgeBaseId) {
        KnowledgeEvaluationAccess.KnowledgeEvaluationContext context = knowledge.context(tenantId, knowledgeBaseId);
        List<EvaluationCase> cases = evaluations.listCases(tenantId, knowledgeBaseId).stream().filter(EvaluationCase::enabled).toList();
        if (cases.isEmpty()) throw new IllegalArgumentException("create at least one evaluation case before running");
        EvaluationRun run = evaluations.createRun(tenantId, knowledgeBaseId, context.knowledgeBaseVersion(), cases.size());
        int evaluated = 0;
        int failed = 0;
        int recallAt1 = 0;
        int recallAt3 = 0;
        int recallAt6 = 0;
        for (EvaluationCase evaluationCase : cases) {
            long started = System.nanoTime();
            try {
                List<KnowledgeEvaluationAccess.KnowledgeEvaluationCitation> citations = knowledge.retrieve(tenantId, knowledgeBaseId, evaluationCase.question());
                Integer hitRank = citations.stream().filter(citation -> citation.documentId().equals(evaluationCase.expectedDocumentId())).map(KnowledgeEvaluationAccess.KnowledgeEvaluationCitation::rank).findFirst().orElse(null);
                Double topScore = citations.isEmpty() ? null : citations.getFirst().score();
                long latencyMs = (System.nanoTime() - started) / 1_000_000;
                evaluations.saveResult(tenantId, run.id(), evaluationCase.id(), evaluationCase.expectedDocumentId(), hitRank, topScore, latencyMs);
                evaluated++;
                if (hitRank != null && hitRank <= 1) recallAt1++;
                if (hitRank != null && hitRank <= 3) recallAt3++;
                if (hitRank != null && hitRank <= 6) recallAt6++;
            } catch (RuntimeException ignored) {
                evaluations.saveFailedResult(tenantId, run.id(), evaluationCase.id(), evaluationCase.expectedDocumentId(), (System.nanoTime() - started) / 1_000_000, "RETRIEVAL_FAILED");
                failed++;
            }
        }
        Double denominator = evaluated == 0 ? null : (double) evaluated;
        evaluations.completeRun(tenantId, run.id(), evaluated, failed, denominator == null ? null : recallAt1 / denominator, denominator == null ? null : recallAt3 / denominator, denominator == null ? null : recallAt6 / denominator);
        return getRun(tenantId, run.id());
    }
}
