package com.lqq.supportflow.evaluation.api;

import com.lqq.supportflow.evaluation.application.ManageRetrievalEvaluationService;
import com.lqq.supportflow.evaluation.domain.EvaluationCase;
import com.lqq.supportflow.evaluation.domain.EvaluationRun;
import com.lqq.supportflow.evaluation.domain.EvaluationRunDetails;
import com.lqq.supportflow.shared.AuthenticatedPrincipal;
import jakarta.validation.Valid;
import java.net.URI;
import java.util.List;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/admin/evaluations")
public class AdminEvaluationController {
    private final ManageRetrievalEvaluationService evaluations;

    public AdminEvaluationController(ManageRetrievalEvaluationService evaluations) { this.evaluations = evaluations; }

    @GetMapping("/cases")
    List<EvaluationCase> listCases(@AuthenticationPrincipal AuthenticatedPrincipal principal, @RequestParam Long knowledgeBaseId) {
        return evaluations.listCases(principal.tenantId(), knowledgeBaseId);
    }

    @PostMapping("/cases")
    ResponseEntity<EvaluationCase> createCase(@AuthenticationPrincipal AuthenticatedPrincipal principal, @RequestParam Long knowledgeBaseId, @Valid @RequestBody CreateEvaluationCaseRequest request) {
        EvaluationCase created = evaluations.createCase(principal.tenantId(), knowledgeBaseId, request.question(), request.expectedDocumentId(), request.category());
        return ResponseEntity.created(URI.create("/api/v1/admin/evaluations/cases/" + created.id())).body(created);
    }

    @DeleteMapping("/cases/{caseId}")
    ResponseEntity<Void> deleteCase(@AuthenticationPrincipal AuthenticatedPrincipal principal, @RequestParam Long knowledgeBaseId, @PathVariable Long caseId) {
        evaluations.deleteCase(principal.tenantId(), knowledgeBaseId, caseId);
        return ResponseEntity.noContent().build();
    }

    @GetMapping("/runs")
    List<EvaluationRun> listRuns(@AuthenticationPrincipal AuthenticatedPrincipal principal, @RequestParam Long knowledgeBaseId) {
        return evaluations.listRuns(principal.tenantId(), knowledgeBaseId);
    }

    @PostMapping("/runs")
    ResponseEntity<EvaluationRunDetails> run(@AuthenticationPrincipal AuthenticatedPrincipal principal, @RequestParam Long knowledgeBaseId) {
        EvaluationRunDetails completed = evaluations.run(principal.tenantId(), knowledgeBaseId);
        return ResponseEntity.created(URI.create("/api/v1/admin/evaluations/runs/" + completed.run().id())).body(completed);
    }

    @GetMapping("/runs/{runId}")
    EvaluationRunDetails getRun(@AuthenticationPrincipal AuthenticatedPrincipal principal, @PathVariable Long runId) {
        return evaluations.getRun(principal.tenantId(), runId);
    }
}
