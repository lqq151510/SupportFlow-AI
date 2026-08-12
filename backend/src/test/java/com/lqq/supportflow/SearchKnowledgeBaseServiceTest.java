package com.lqq.supportflow;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;
import com.lqq.supportflow.knowledge.application.SearchKnowledgeBaseService;
import com.lqq.supportflow.knowledge.domain.*;
import com.lqq.supportflow.model.ModelEmbeddingService;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.*;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class SearchKnowledgeBaseServiceTest {
    @Mock private KnowledgeBasePort bases;
    @Mock private KnowledgeSearchIndex index;
    @Mock private ModelEmbeddingService embeddings;
    @Mock private KnowledgeSearchAuditPort audits;

    @Test
    void mergesTenantScopedKeywordAndVectorResultsUsingRrf() {
        when(bases.findById(1L, 2L)).thenReturn(Optional.of(new KnowledgeBase(2L, "Policies", "", "ACTIVE", 7L)));
        when(index.keywordSearch(1L, 2L, "refund policy", 20)).thenReturn(List.of(new RankedKnowledgeChunk(10L, 100L, "Refund policy", 5), new RankedKnowledgeChunk(11L, 101L, "Shipping policy", 2)));
        when(embeddings.embed(1L, List.of("refund policy"))).thenReturn(List.of(new float[]{0.2f, 0.4f}));
        when(index.vectorSearch(eq(1L), eq(2L), any(float[].class), eq(20))).thenReturn(List.of(new RankedKnowledgeChunk(10L, 100L, "Refund policy", 0.9)));
        when(audits.save(eq(1L), eq(2L), eq(7L), eq("refund policy"), anyList())).thenReturn(300L);

        KnowledgeSearchResult result = new SearchKnowledgeBaseService(bases, index, embeddings, audits, 0.015).search(1L, 2L, "refund policy");
        List<KnowledgeCitation> citations = result.citations();

        assertThat(result.searchId()).isEqualTo(300L);
        assertThat(citations).hasSize(2);
        assertThat(citations.getFirst().chunkId()).isEqualTo(10L);
        assertThat(citations.getFirst().rank()).isEqualTo(1);
        verify(index).keywordSearch(1L, 2L, "refund policy", 20);
        verify(index).vectorSearch(eq(1L), eq(2L), any(float[].class), eq(20));
    }

    @Test
    void appliesConfiguredRrfThreshold() {
        when(bases.findById(1L, 2L)).thenReturn(Optional.of(new KnowledgeBase(2L, "Policies", "", "ACTIVE", 3L)));
        when(index.keywordSearch(1L, 2L, "weak", 20)).thenReturn(List.of(new RankedKnowledgeChunk(10L, 100L, "Weak", 1)));
        when(embeddings.embed(1L, List.of("weak"))).thenReturn(List.of(new float[]{0.1f}));
        when(index.vectorSearch(eq(1L), eq(2L), any(float[].class), eq(20))).thenReturn(List.of());
        when(audits.save(eq(1L), eq(2L), eq(3L), eq("weak"), anyList())).thenReturn(301L);

        KnowledgeSearchResult result = new SearchKnowledgeBaseService(bases, index, embeddings, audits, 0.02).search(1L, 2L, "weak");

        assertThat(result.citations()).isEmpty();
    }
}
