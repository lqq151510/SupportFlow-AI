package com.lqq.supportflow;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import com.lqq.supportflow.knowledge.KnowledgeRetrievalService;
import com.lqq.supportflow.knowledge.application.SearchKnowledgeBaseService;
import com.lqq.supportflow.knowledge.domain.KnowledgeBase;
import com.lqq.supportflow.knowledge.domain.KnowledgeBasePort;
import com.lqq.supportflow.knowledge.domain.KnowledgeCitation;
import com.lqq.supportflow.knowledge.domain.KnowledgeSearchResult;
import java.util.List;
import org.junit.jupiter.api.Test;

class KnowledgeRetrievalServiceTest {
    @Test
    void mergesOnlyTenantKnowledgeBaseResultsByScore() {
        KnowledgeBasePort bases = mock(KnowledgeBasePort.class); SearchKnowledgeBaseService search = mock(SearchKnowledgeBaseService.class);
        when(bases.list(7L)).thenReturn(List.of(new KnowledgeBase(2L, "Returns", "", "ACTIVE", 1L)));
        when(search.search(7L, 2L, "refund")).thenReturn(new KnowledgeSearchResult(3L, List.of(new KnowledgeCitation(4L, 5L, "30-day refund policy", 0.9, 1))));
        assertThat(new KnowledgeRetrievalService(bases, search, 0.5, 1).retrieve(7L, "refund")).singleElement().satisfies(citation -> { assertThat(citation.knowledgeBaseId()).isEqualTo(2L); assertThat(citation.content()).isEqualTo("30-day refund policy"); assertThat(citation.rank()).isEqualTo(1); });
    }

    @Test
    void rejectsResultsBelowConfiguredEvidenceThreshold() {
        KnowledgeBasePort bases = mock(KnowledgeBasePort.class); SearchKnowledgeBaseService search = mock(SearchKnowledgeBaseService.class);
        when(bases.list(7L)).thenReturn(List.of(new KnowledgeBase(2L, "Returns", "", "ACTIVE", 1L)));
        when(search.search(7L, 2L, "refund")).thenReturn(new KnowledgeSearchResult(3L, List.of(new KnowledgeCitation(4L, 5L, "weak match", 0.4, 1))));
        assertThat(new KnowledgeRetrievalService(bases, search, 0.5, 1).retrieve(7L, "refund")).isEmpty();
    }
}
