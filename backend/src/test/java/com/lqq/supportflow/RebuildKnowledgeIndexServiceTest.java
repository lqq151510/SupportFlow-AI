package com.lqq.supportflow;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import com.lqq.supportflow.knowledge.application.RebuildKnowledgeIndexService;
import com.lqq.supportflow.knowledge.domain.IndexedKnowledgeChunk;
import com.lqq.supportflow.knowledge.domain.IngestionStatus;
import com.lqq.supportflow.knowledge.domain.KnowledgeChunk;
import com.lqq.supportflow.knowledge.domain.KnowledgeChunkPort;
import com.lqq.supportflow.knowledge.domain.KnowledgeDocument;
import com.lqq.supportflow.knowledge.domain.KnowledgeDocumentPort;
import com.lqq.supportflow.knowledge.domain.KnowledgeSearchIndex;
import com.lqq.supportflow.model.ModelEmbeddingService;
import java.util.List;
import org.junit.jupiter.api.Test;

class RebuildKnowledgeIndexServiceTest {

    @Test
    void onlyRebuildsIndexedDocumentsWithChunksAndCountsIndexedEntries() {
        KnowledgeDocumentPort documents = mock(KnowledgeDocumentPort.class);
        KnowledgeChunkPort chunks = mock(KnowledgeChunkPort.class);
        ModelEmbeddingService embeddings = mock(ModelEmbeddingService.class);
        KnowledgeSearchIndex index = mock(KnowledgeSearchIndex.class);
        when(documents.findByKnowledgeBase(7L, 8L)).thenReturn(List.of(
                new KnowledgeDocument(1L, "pending.md", "a", IngestionStatus.EMBEDDING),
                new KnowledgeDocument(2L, "empty.md", "b", IngestionStatus.INDEXED),
                new KnowledgeDocument(3L, "indexed.md", "c", IngestionStatus.INDEXED)));
        when(chunks.findByDocument(7L, 8L, 2L)).thenReturn(List.of());
        List<KnowledgeChunk> source = List.of(new KnowledgeChunk(31L, 3L, 0, "first"), new KnowledgeChunk(32L, 3L, 1, "second"));
        when(chunks.findByDocument(7L, 8L, 3L)).thenReturn(source);
        when(embeddings.embed(7L, List.of("first", "second"))).thenReturn(List.of(new float[] {1F}, new float[] {2F}));

        int rebuilt = new RebuildKnowledgeIndexService(documents, chunks, embeddings, index).rebuild(7L, 8L);

        assertThat(rebuilt).isEqualTo(2);
        verify(index).index(org.mockito.ArgumentMatchers.eq(7L), org.mockito.ArgumentMatchers.eq(8L), org.mockito.ArgumentMatchers.eq(3L),
                org.mockito.ArgumentMatchers.argThat(entries -> entries.stream().map(IndexedKnowledgeChunk::chunk).toList().equals(source)));
    }

    @Test
    void returnsZeroWithoutDocuments() {
        KnowledgeDocumentPort documents = mock(KnowledgeDocumentPort.class);
        when(documents.findByKnowledgeBase(7L, 8L)).thenReturn(List.of());
        KnowledgeChunkPort chunks = mock(KnowledgeChunkPort.class);
        ModelEmbeddingService embeddings = mock(ModelEmbeddingService.class);
        KnowledgeSearchIndex index = mock(KnowledgeSearchIndex.class);

        assertThat(new RebuildKnowledgeIndexService(documents, chunks, embeddings, index).rebuild(7L, 8L)).isZero();
        verifyNoInteractions(chunks, embeddings, index);
    }
}
