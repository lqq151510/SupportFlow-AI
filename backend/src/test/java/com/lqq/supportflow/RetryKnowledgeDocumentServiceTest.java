package com.lqq.supportflow;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.inOrder;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.lqq.supportflow.knowledge.application.KnowledgeIndexingFailureHandler;
import com.lqq.supportflow.knowledge.application.RetryKnowledgeDocumentService;
import com.lqq.supportflow.knowledge.domain.IngestionStatus;
import com.lqq.supportflow.knowledge.domain.KnowledgeDocument;
import com.lqq.supportflow.knowledge.domain.KnowledgeDocumentPort;
import java.util.Optional;
import org.junit.jupiter.api.Test;
import org.mockito.InOrder;

class RetryKnowledgeDocumentServiceTest {

    @Test
    void resumesFailedDocumentsThroughTheRequiredStatesBeforeIndexing() {
        KnowledgeDocumentPort documents = mock(KnowledgeDocumentPort.class);
        KnowledgeIndexingFailureHandler indexing = mock(KnowledgeIndexingFailureHandler.class);
        RetryKnowledgeDocumentService service = new RetryKnowledgeDocumentService(documents, indexing);
        KnowledgeDocument failed = document(IngestionStatus.FAILED);
        KnowledgeDocument parsing = document(IngestionStatus.PARSING);
        KnowledgeDocument chunking = document(IngestionStatus.CHUNKING);
        KnowledgeDocument embedding = document(IngestionStatus.EMBEDDING);
        KnowledgeDocument indexed = document(IngestionStatus.INDEXED);
        when(documents.findById(7L, 8L, 30L)).thenReturn(Optional.of(failed));
        when(documents.transitionStatus(7L, 30L, IngestionStatus.FAILED, IngestionStatus.PARSING))
                .thenReturn(parsing);
        when(documents.transitionStatus(7L, 30L, IngestionStatus.PARSING, IngestionStatus.CHUNKING))
                .thenReturn(chunking);
        when(documents.transitionStatus(7L, 30L, IngestionStatus.CHUNKING, IngestionStatus.EMBEDDING))
                .thenReturn(embedding);
        when(indexing.index(7L, 8L, 30L)).thenReturn(indexed);

        assertThat(service.retry(7L, 8L, 30L)).isSameAs(indexed);

        InOrder order = inOrder(documents, indexing);
        order.verify(documents).transitionStatus(
                7L, 30L, IngestionStatus.FAILED, IngestionStatus.PARSING);
        order.verify(documents).transitionStatus(
                7L, 30L, IngestionStatus.PARSING, IngestionStatus.CHUNKING);
        order.verify(documents).transitionStatus(
                7L, 30L, IngestionStatus.CHUNKING, IngestionStatus.EMBEDDING);
        order.verify(indexing).index(7L, 8L, 30L);
    }

    @Test
    void retriesDocumentsAlreadyWaitingForEmbeddingWithoutReplayingTransitions() {
        KnowledgeDocumentPort documents = mock(KnowledgeDocumentPort.class);
        KnowledgeIndexingFailureHandler indexing = mock(KnowledgeIndexingFailureHandler.class);
        RetryKnowledgeDocumentService service = new RetryKnowledgeDocumentService(documents, indexing);
        KnowledgeDocument embedding = document(IngestionStatus.EMBEDDING);
        KnowledgeDocument indexed = document(IngestionStatus.INDEXED);
        when(documents.findById(7L, 8L, 30L)).thenReturn(Optional.of(embedding));
        when(indexing.index(7L, 8L, 30L)).thenReturn(indexed);

        assertThat(service.retry(7L, 8L, 30L)).isSameAs(indexed);
        verify(documents, never()).transitionStatus(
                7L, 30L, IngestionStatus.FAILED, IngestionStatus.PARSING);
    }

    @Test
    void rejectsForeignAndNonRetryableDocuments() {
        KnowledgeDocumentPort documents = mock(KnowledgeDocumentPort.class);
        KnowledgeIndexingFailureHandler indexing = mock(KnowledgeIndexingFailureHandler.class);
        RetryKnowledgeDocumentService service = new RetryKnowledgeDocumentService(documents, indexing);
        when(documents.findById(7L, 8L, 30L)).thenReturn(Optional.empty());
        when(documents.findById(7L, 8L, 31L)).thenReturn(Optional.of(document(IngestionStatus.INDEXED)));

        assertThatThrownBy(() -> service.retry(7L, 8L, 30L))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("document does not belong to tenant");
        assertThatThrownBy(() -> service.retry(7L, 8L, 31L))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("document is not retryable");
        verify(indexing, never()).index(7L, 8L, 31L);
    }

    private KnowledgeDocument document(IngestionStatus status) {
        return new KnowledgeDocument(30L, "refund.md", "hash", status);
    }
}
