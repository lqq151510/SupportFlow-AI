package com.lqq.supportflow;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.lqq.supportflow.knowledge.application.KnowledgeIndexingFailureHandler;
import com.lqq.supportflow.knowledge.application.KnowledgeFilePolicy;
import com.lqq.supportflow.knowledge.application.RegisterKnowledgeDocumentService;
import com.lqq.supportflow.knowledge.application.UploadKnowledgeDocumentService;
import com.lqq.supportflow.knowledge.domain.DocumentTextExtractor;
import com.lqq.supportflow.knowledge.domain.IngestionStatus;
import com.lqq.supportflow.knowledge.domain.KnowledgeDocument;
import com.lqq.supportflow.knowledge.domain.KnowledgeDocumentPort;
import com.lqq.supportflow.knowledge.domain.KnowledgeObjectStorage;
import com.lqq.supportflow.knowledge.domain.StoredKnowledgeObject;
import java.io.ByteArrayInputStream;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockMultipartFile;

class UploadKnowledgeDocumentServiceTest {
    @Test
    void storesExtractsAndIndexesAnAcceptedDocument() {
        KnowledgeObjectStorage storage = mock(KnowledgeObjectStorage.class);
        DocumentTextExtractor extractor = mock(DocumentTextExtractor.class);
        RegisterKnowledgeDocumentService registration = mock(RegisterKnowledgeDocumentService.class);
        KnowledgeDocumentPort documents = mock(KnowledgeDocumentPort.class);
        KnowledgeIndexingFailureHandler indexing = mock(KnowledgeIndexingFailureHandler.class);
        byte[] content = "# Refund policy".getBytes(java.nio.charset.StandardCharsets.UTF_8);
        when(storage.put(any(), any(), any(), any(), any(), any(), anyLong()))
                .thenReturn(new StoredKnowledgeObject("tenants/7/object", content.length, "text/markdown"));
        when(storage.open("tenants/7/object")).thenReturn(new ByteArrayInputStream(content));
        when(extractor.extract(any(), any())).thenReturn("Refund policy");
        when(registration.registerExtracted(any(), any(), any(), any(), any()))
                .thenReturn(new KnowledgeDocument(30L, "refund.md", "hash", IngestionStatus.EMBEDDING));
        KnowledgeDocument indexed = new KnowledgeDocument(30L, "refund.md", "hash", IngestionStatus.INDEXED);
        when(indexing.index(7L, 8L, 30L)).thenReturn(indexed);
        UploadKnowledgeDocumentService service = new UploadKnowledgeDocumentService(
                storage, extractor, registration, documents, indexing, new KnowledgeFilePolicy());

        KnowledgeDocument result = service.upload(7L, 8L,
                new MockMultipartFile("file", "refund.md", "text/markdown", content));

        assertThat(result.status()).isEqualTo(IngestionStatus.INDEXED);
        verify(documents).attachObject(7L, 30L, "tenants/7/object", "text/markdown");
        verify(indexing).index(7L, 8L, 30L);
    }
}
