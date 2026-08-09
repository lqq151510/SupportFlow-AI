package com.lqq.supportflow;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;
import com.lqq.supportflow.knowledge.application.IndexKnowledgeDocumentService;
import com.lqq.supportflow.knowledge.domain.*;
import com.lqq.supportflow.model.ModelEmbeddingService;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.*;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class IndexKnowledgeDocumentServiceTest {
    @Mock private KnowledgeDocumentPort documents;
    @Mock private KnowledgeChunkPort chunks;
    @Mock private ModelEmbeddingService embeddings;
    @Mock private KnowledgeSearchIndex index;
    @InjectMocks private IndexKnowledgeDocumentService service;

    @Test
    void embedsAndIndexesTenantScopedChunksBeforeMarkingDocumentIndexed() {
        KnowledgeDocument document = new KnowledgeDocument(30L, "returns.md", "hash", IngestionStatus.EMBEDDING);
        KnowledgeChunk chunk = new KnowledgeChunk(40L, 30L, 0, "Returns within 30 days");
        when(documents.findById(1L, 2L, 30L)).thenReturn(Optional.of(document));
        when(chunks.findByDocument(1L, 2L, 30L)).thenReturn(List.of(chunk));
        when(embeddings.embed(1L, List.of(chunk.content()))).thenReturn(List.of(new float[]{0.1f, 0.2f}));
        when(documents.transitionStatus(1L, 30L, IngestionStatus.EMBEDDING, IngestionStatus.INDEXING)).thenReturn(new KnowledgeDocument(30L, "returns.md", "hash", IngestionStatus.INDEXING));
        when(documents.transitionStatus(1L, 30L, IngestionStatus.INDEXING, IngestionStatus.INDEXED)).thenReturn(new KnowledgeDocument(30L, "returns.md", "hash", IngestionStatus.INDEXED));

        KnowledgeDocument result = service.index(1L, 2L, 30L);

        assertThat(result.status()).isEqualTo(IngestionStatus.INDEXED);
        verify(index).index(eq(1L), eq(2L), eq(30L), argThat(entries -> entries.size() == 1 && entries.getFirst().chunk().id().equals(40L)));
    }
}
