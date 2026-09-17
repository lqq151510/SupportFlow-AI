package com.lqq.supportflow;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

import com.lqq.supportflow.evaluation.application.ManageRetrievalEvaluationService;
import com.lqq.supportflow.evaluation.domain.*;
import com.lqq.supportflow.knowledge.KnowledgeEvaluationAccess;
import java.time.Instant;
import java.util.List;
import java.util.Optional;
import org.junit.jupiter.api.Test;

class ManageRetrievalEvaluationServiceTest {
    @Test
    void runsTenantScopedCasesAgainstActualRetrievalAndAggregatesRecall() {
        EvaluationPort evaluations = mock(EvaluationPort.class);
        KnowledgeEvaluationAccess knowledge = mock(KnowledgeEvaluationAccess.class);
        when(knowledge.context(1L, 20L)).thenReturn(new KnowledgeEvaluationAccess.KnowledgeEvaluationContext(7L));
        EvaluationCase first = new EvaluationCase(100L, 20L, "退款多久到账", 30L, "REFUND", true, Instant.now());
        EvaluationCase second = new EvaluationCase(101L, 20L, "物流如何查询", 31L, "DELIVERY", true, Instant.now());
        when(evaluations.listCases(1L, 20L)).thenReturn(List.of(first, second));
        EvaluationRun running = new EvaluationRun(200L, 20L, 7L, "RUNNING", 2, 0, 0, null, null, null, Instant.now(), null);
        EvaluationRun completed = new EvaluationRun(200L, 20L, 7L, "COMPLETED", 2, 2, 0, .5, 1.0, 1.0, Instant.now(), Instant.now());
        when(evaluations.createRun(1L, 20L, 7L, 2)).thenReturn(running);
        when(knowledge.retrieve(1L, 20L, first.question())).thenReturn(List.of(new KnowledgeEvaluationAccess.KnowledgeEvaluationCitation(30L, 1, .8)));
        when(knowledge.retrieve(1L, 20L, second.question())).thenReturn(List.of(new KnowledgeEvaluationAccess.KnowledgeEvaluationCitation(99L, 1, .9), new KnowledgeEvaluationAccess.KnowledgeEvaluationCitation(31L, 2, .7)));
        when(evaluations.findRun(1L, 200L)).thenReturn(Optional.of(completed));
        when(evaluations.listResults(1L, 200L)).thenReturn(List.of());

        EvaluationRunDetails details = new ManageRetrievalEvaluationService(evaluations, knowledge).run(1L, 20L);

        assertThat(details.run().recallAt1()).isEqualTo(.5);
        assertThat(details.run().recallAt3()).isEqualTo(1.0);
        verify(evaluations).saveResult(eq(1L), eq(200L), eq(100L), eq(30L), eq(1), eq(.8), anyLong());
        verify(evaluations).saveResult(eq(1L), eq(200L), eq(101L), eq(31L), eq(2), eq(.9), anyLong());
        verify(evaluations).completeRun(1L, 200L, 2, 0, .5, 1.0, 1.0);
        verify(knowledge, times(2)).retrieve(eq(1L), eq(20L), anyString());
    }

    @Test
    void recordsRetrievalFailuresWithoutInventingQualityMetrics() {
        EvaluationPort evaluations = mock(EvaluationPort.class);
        KnowledgeEvaluationAccess knowledge = mock(KnowledgeEvaluationAccess.class);
        when(knowledge.context(1L, 20L)).thenReturn(new KnowledgeEvaluationAccess.KnowledgeEvaluationContext(1L));
        EvaluationCase item = new EvaluationCase(100L, 20L, "退款多久到账", 30L, "REFUND", true, Instant.now());
        when(evaluations.listCases(1L, 20L)).thenReturn(List.of(item));
        when(evaluations.createRun(1L, 20L, 1L, 1)).thenReturn(new EvaluationRun(200L, 20L, 1L, "RUNNING", 1, 0, 0, null, null, null, Instant.now(), null));
        when(knowledge.retrieve(1L, 20L, item.question())).thenThrow(new IllegalStateException("provider detail must not escape"));
        when(evaluations.findRun(1L, 200L)).thenReturn(Optional.of(new EvaluationRun(200L, 20L, 1L, "COMPLETED", 1, 0, 1, null, null, null, Instant.now(), Instant.now())));
        when(evaluations.listResults(1L, 200L)).thenReturn(List.of());

        new ManageRetrievalEvaluationService(evaluations, knowledge).run(1L, 20L);

        verify(evaluations).saveFailedResult(eq(1L), eq(200L), eq(100L), eq(30L), anyLong(), eq("RETRIEVAL_FAILED"));
        verify(evaluations).completeRun(1L, 200L, 0, 1, null, null, null);
    }

    @Test
    void validatesCasesAndNormalizesAnUnsetCategory() {
        EvaluationPort evaluations = mock(EvaluationPort.class);
        KnowledgeEvaluationAccess knowledge = mock(KnowledgeEvaluationAccess.class);
        when(knowledge.context(1L, 20L)).thenReturn(new KnowledgeEvaluationAccess.KnowledgeEvaluationContext(1L));
        ManageRetrievalEvaluationService service = new ManageRetrievalEvaluationService(evaluations, knowledge);

        assertThatThrownBy(() -> service.createCase(1L, 20L, null, 30L, null))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("evaluation question is required");

        EvaluationCase created = new EvaluationCase(100L, 20L, "退款多久到账", 30L, "GENERAL", true, Instant.now());
        when(evaluations.createCase(1L, 20L, "退款多久到账", 30L, "GENERAL")).thenReturn(created);

        assertThat(service.createCase(1L, 20L, " 退款多久到账 ", 30L, null)).isSameAs(created);
        verify(knowledge, times(2)).requireDocument(1L, 20L, 30L);
    }

    @Test
    void refusesRunsWithoutEnabledCases() {
        EvaluationPort evaluations = mock(EvaluationPort.class);
        KnowledgeEvaluationAccess knowledge = mock(KnowledgeEvaluationAccess.class);
        when(knowledge.context(1L, 20L)).thenReturn(new KnowledgeEvaluationAccess.KnowledgeEvaluationContext(1L));
        when(evaluations.listCases(1L, 20L)).thenReturn(List.of(new EvaluationCase(100L, 20L, "退款多久到账", 30L, "REFUND", false, Instant.now())));

        assertThatThrownBy(() -> new ManageRetrievalEvaluationService(evaluations, knowledge).run(1L, 20L))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("create at least one evaluation case before running");
    }

    @Test
    void recordsACompletedNoHitWithoutClaimingARecall() {
        EvaluationPort evaluations = mock(EvaluationPort.class);
        KnowledgeEvaluationAccess knowledge = mock(KnowledgeEvaluationAccess.class);
        when(knowledge.context(1L, 20L)).thenReturn(new KnowledgeEvaluationAccess.KnowledgeEvaluationContext(1L));
        EvaluationCase item = new EvaluationCase(100L, 20L, "退款多久到账", 30L, "REFUND", true, Instant.now());
        when(evaluations.listCases(1L, 20L)).thenReturn(List.of(item));
        when(evaluations.createRun(1L, 20L, 1L, 1)).thenReturn(new EvaluationRun(200L, 20L, 1L, "RUNNING", 1, 0, 0, null, null, null, Instant.now(), null));
        when(knowledge.retrieve(1L, 20L, item.question())).thenReturn(List.of());
        when(evaluations.findRun(1L, 200L)).thenReturn(Optional.of(new EvaluationRun(200L, 20L, 1L, "COMPLETED", 1, 1, 0, 0.0, 0.0, 0.0, Instant.now(), Instant.now())));
        when(evaluations.listResults(1L, 200L)).thenReturn(List.of());

        new ManageRetrievalEvaluationService(evaluations, knowledge).run(1L, 20L);

        verify(evaluations).saveResult(eq(1L), eq(200L), eq(100L), eq(30L), isNull(), isNull(), anyLong());
        verify(evaluations).completeRun(1L, 200L, 1, 0, 0.0, 0.0, 0.0);
    }
}
