package com.lqq.supportflow.evaluation.infrastructure;

import com.lqq.supportflow.evaluation.domain.EvaluationCase;
import com.lqq.supportflow.evaluation.domain.EvaluationPort;
import com.lqq.supportflow.evaluation.domain.EvaluationResult;
import com.lqq.supportflow.evaluation.domain.EvaluationRun;
import com.baomidou.mybatisplus.core.toolkit.IdWorker;
import java.sql.ResultSet;
import java.time.Instant;
import java.util.List;
import java.util.Optional;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

@Component
public class JdbcEvaluationAdapter implements EvaluationPort {
    private final JdbcTemplate jdbc;

    public JdbcEvaluationAdapter(JdbcTemplate jdbc) { this.jdbc = jdbc; }

    @Override
    public EvaluationCase createCase(Long tenantId, Long knowledgeBaseId, String question, Long expectedDocumentId, String category) {
        long id = IdWorker.getId();
        Instant now = Instant.now();
        jdbc.update("INSERT INTO evaluation_cases(id, tenant_id, knowledge_base_id, question, expected_document_id, category, enabled, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, TRUE, ?, ?)", id, tenantId, knowledgeBaseId, question, expectedDocumentId, category, now, now);
        return new EvaluationCase(id, knowledgeBaseId, question, expectedDocumentId, category, true, now);
    }

    @Override
    public List<EvaluationCase> listCases(Long tenantId, Long knowledgeBaseId) {
        return jdbc.query("SELECT id, knowledge_base_id, question, expected_document_id, category, enabled, created_at FROM evaluation_cases WHERE tenant_id = ? AND knowledge_base_id = ? ORDER BY created_at DESC", (rs, ignored) -> caseOf(rs), tenantId, knowledgeBaseId);
    }

    @Override
    public void deleteCase(Long tenantId, Long knowledgeBaseId, Long caseId) {
        if (jdbc.update("DELETE FROM evaluation_cases WHERE id = ? AND tenant_id = ? AND knowledge_base_id = ?", caseId, tenantId, knowledgeBaseId) != 1) {
            throw new IllegalArgumentException("evaluation case does not belong to tenant");
        }
    }

    @Override
    public EvaluationRun createRun(Long tenantId, Long knowledgeBaseId, long knowledgeBaseVersion, int totalCases) {
        long id = IdWorker.getId();
        Instant now = Instant.now();
        jdbc.update("INSERT INTO evaluation_runs(id, tenant_id, knowledge_base_id, knowledge_base_version, status, total_cases, evaluated_cases, failed_cases, started_at) VALUES (?, ?, ?, ?, 'RUNNING', ?, 0, 0, ?)", id, tenantId, knowledgeBaseId, knowledgeBaseVersion, totalCases, now);
        return new EvaluationRun(id, knowledgeBaseId, knowledgeBaseVersion, "RUNNING", totalCases, 0, 0, null, null, null, now, null);
    }

    @Override
    public void saveResult(Long tenantId, Long runId, Long caseId, Long expectedDocumentId, Integer hitRank, Double topScore, long latencyMs) {
        jdbc.update("INSERT INTO evaluation_results(id, tenant_id, run_id, case_id, status, expected_document_id, hit_rank, top_score, latency_ms, created_at) VALUES (?, ?, ?, ?, 'COMPLETED', ?, ?, ?, ?, ?)", IdWorker.getId(), tenantId, runId, caseId, expectedDocumentId, hitRank, topScore, latencyMs, Instant.now());
    }

    @Override
    public void saveFailedResult(Long tenantId, Long runId, Long caseId, Long expectedDocumentId, long latencyMs, String failureCode) {
        jdbc.update("INSERT INTO evaluation_results(id, tenant_id, run_id, case_id, status, expected_document_id, latency_ms, failure_code, created_at) VALUES (?, ?, ?, ?, 'FAILED', ?, ?, ?, ?)", IdWorker.getId(), tenantId, runId, caseId, expectedDocumentId, latencyMs, failureCode, Instant.now());
    }

    @Override
    public void completeRun(Long tenantId, Long runId, int evaluatedCases, int failedCases, Double recallAt1, Double recallAt3, Double recallAt6) {
        if (jdbc.update("UPDATE evaluation_runs SET status = 'COMPLETED', evaluated_cases = ?, failed_cases = ?, recall_at_1 = ?, recall_at_3 = ?, recall_at_6 = ?, completed_at = ? WHERE id = ? AND tenant_id = ? AND status = 'RUNNING'", evaluatedCases, failedCases, recallAt1, recallAt3, recallAt6, Instant.now(), runId, tenantId) != 1) {
            throw new IllegalArgumentException("evaluation run does not belong to tenant");
        }
    }

    @Override
    public Optional<EvaluationRun> findRun(Long tenantId, Long runId) {
        return jdbc.query("SELECT * FROM evaluation_runs WHERE id = ? AND tenant_id = ?", rs -> rs.next() ? Optional.of(runOf(rs)) : Optional.empty(), runId, tenantId);
    }

    @Override
    public List<EvaluationRun> listRuns(Long tenantId, Long knowledgeBaseId) {
        return jdbc.query("SELECT * FROM evaluation_runs WHERE tenant_id = ? AND knowledge_base_id = ? ORDER BY started_at DESC", (rs, ignored) -> runOf(rs), tenantId, knowledgeBaseId);
    }

    @Override
    public List<EvaluationResult> listResults(Long tenantId, Long runId) {
        return jdbc.query("SELECT * FROM evaluation_results WHERE tenant_id = ? AND run_id = ? ORDER BY created_at ASC", (rs, ignored) -> resultOf(rs), tenantId, runId);
    }

    private EvaluationCase caseOf(ResultSet rs) throws java.sql.SQLException { return new EvaluationCase(rs.getLong("id"), rs.getLong("knowledge_base_id"), rs.getString("question"), rs.getLong("expected_document_id"), rs.getString("category"), rs.getBoolean("enabled"), rs.getTimestamp("created_at").toInstant()); }
    private EvaluationRun runOf(ResultSet rs) throws java.sql.SQLException { return new EvaluationRun(rs.getLong("id"), rs.getLong("knowledge_base_id"), rs.getLong("knowledge_base_version"), rs.getString("status"), rs.getInt("total_cases"), rs.getInt("evaluated_cases"), rs.getInt("failed_cases"), number(rs, "recall_at_1"), number(rs, "recall_at_3"), number(rs, "recall_at_6"), rs.getTimestamp("started_at").toInstant(), rs.getTimestamp("completed_at") == null ? null : rs.getTimestamp("completed_at").toInstant()); }
    private EvaluationResult resultOf(ResultSet rs) throws java.sql.SQLException { return new EvaluationResult(rs.getLong("id"), rs.getLong("case_id"), rs.getString("status"), rs.getLong("expected_document_id"), integer(rs, "hit_rank"), number(rs, "top_score"), longValue(rs, "latency_ms"), rs.getString("failure_code"), rs.getTimestamp("created_at").toInstant()); }
    private Double number(ResultSet rs, String column) throws java.sql.SQLException { var value = rs.getBigDecimal(column); return value == null ? null : value.doubleValue(); }
    private Integer integer(ResultSet rs, String column) throws java.sql.SQLException { int value = rs.getInt(column); return rs.wasNull() ? null : value; }
    private Long longValue(ResultSet rs, String column) throws java.sql.SQLException { long value = rs.getLong(column); return rs.wasNull() ? null : value; }
}
