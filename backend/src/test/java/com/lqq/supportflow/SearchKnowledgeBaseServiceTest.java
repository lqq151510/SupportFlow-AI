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
    @InjectMocks private SearchKnowledgeBaseService service;

    @Test
    void mergesTenantScopedKeywordAndVectorResultsUsingRrf() {
        when(bases.belongsTo(1L, 2L)).thenReturn(true);
        when(index.keywordSearch(1L, 2L, "refund policy", 20)).thenReturn(List.of(new RankedKnowledgeChunk(10L, 100L, "Refund policy", 5), new RankedKnowledgeChunk(11L, 101L, "Shipping policy", 2)));
        when(embeddings.embed(1L, List.of("refund policy"))).thenReturn(List.of(new float[]{0.2f, 0.4f}));
        when(index.vectorSearch(eq(1L), eq(2L), any(float[].class), eq(20))).thenReturn(List.of(new RankedKnowledgeChunk(10L, 100L, "Refund policy", 0.9)));

        List<KnowledgeCitation> citations = service.search(1L, 2L, "refund policy");

        assertThat(citations).hasSize(2);
        assertThat(citations.getFirst().chunkId()).isEqualTo(10L);
        assertThat(citations.getFirst().rank()).isEqualTo(1);
        verify(index).keywordSearch(1L, 2L, "refund policy", 20);
        verify(index).vectorSearch(eq(1L), eq(2L), any(float[].class), eq(20));
    }
}
