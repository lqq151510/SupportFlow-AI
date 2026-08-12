package com.lqq.supportflow;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.lqq.supportflow.knowledge.application.IndexKnowledgeDocumentService;
import com.lqq.supportflow.knowledge.application.KnowledgeIndexingFailureHandler;
import com.lqq.supportflow.knowledge.domain.IngestionStatus;
import com.lqq.supportflow.knowledge.domain.KnowledgeDocument;
import com.lqq.supportflow.knowledge.domain.KnowledgeDocumentPort;
import com.lqq.supportflow.model.MissingModelConfigurationException;
import org.junit.jupiter.api.Test;

class KnowledgeIndexingFailureHandlerTest {

    @Test
    void distinguishesMissingModelConfigurationFromGenericIndexingFailures() {
        KnowledgeDocumentPort documents = mock(KnowledgeDocumentPort.class);
        IndexKnowledgeDocumentService indexing = mock(IndexKnowledgeDocumentService.class);
        KnowledgeIndexingFailureHandler handler = new KnowledgeIndexingFailureHandler(documents, indexing);
        KnowledgeDocument failed = new KnowledgeDocument(30L, "refund.md", "hash", IngestionStatus.FAILED);
        when(documents.markFailed(7L, 30L, "EMBEDDING_MODEL_NOT_CONFIGURED")).thenReturn(failed);
        when(documents.markFailed(7L, 31L, "INDEXING_FAILED")).thenReturn(failed);
        when(indexing.index(7L, 8L, 30L))
                .thenThrow(new MissingModelConfigurationException("OpenAI-compatible embedding"));
        when(indexing.index(7L, 8L, 31L)).thenThrow(new IllegalStateException("provider unavailable"));

        assertThat(handler.index(7L, 8L, 30L)).isSameAs(failed);
        assertThat(handler.index(7L, 8L, 31L)).isSameAs(failed);

        verify(documents).markFailed(7L, 30L, "EMBEDDING_MODEL_NOT_CONFIGURED");
        verify(documents).markFailed(7L, 31L, "INDEXING_FAILED");
    }
}
