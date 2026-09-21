package com.lqq.supportflow;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import com.lqq.supportflow.knowledge.application.KnowledgeIndexingFailureHandler;
import com.lqq.supportflow.knowledge.application.KnowledgeFilePolicy;
import com.lqq.supportflow.knowledge.application.RegisterKnowledgeDocumentService;
import com.lqq.supportflow.knowledge.application.UploadKnowledgeDocumentService;
import com.lqq.supportflow.knowledge.domain.ContentHasher;
import com.lqq.supportflow.knowledge.domain.DocumentTextExtractor;
import com.lqq.supportflow.knowledge.domain.IngestionStatus;
import com.lqq.supportflow.knowledge.domain.KnowledgeDocument;
import com.lqq.supportflow.knowledge.domain.KnowledgeDocumentPort;
import com.lqq.supportflow.knowledge.domain.KnowledgeObjectStorage;
import com.lqq.supportflow.knowledge.domain.StoredKnowledgeObject;
import com.lqq.supportflow.shared.ConflictException;
import java.io.ByteArrayInputStream;
import java.util.Optional;
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

    @Test
    void rejectsDuplicateContentBeforeTouchingObjectStorage() {
        KnowledgeObjectStorage storage = mock(KnowledgeObjectStorage.class);
        DocumentTextExtractor extractor = mock(DocumentTextExtractor.class);
        RegisterKnowledgeDocumentService registration = mock(RegisterKnowledgeDocumentService.class);
        KnowledgeDocumentPort documents = mock(KnowledgeDocumentPort.class);
        KnowledgeIndexingFailureHandler indexing = mock(KnowledgeIndexingFailureHandler.class);
        byte[] content = "# Refund policy".getBytes(java.nio.charset.StandardCharsets.UTF_8);
        String hash = ContentHasher.sha256(content);
        when(documents.findByContentHash(7L, 8L, hash))
                .thenReturn(Optional.of(new KnowledgeDocument(30L, "refund.md", hash, IngestionStatus.INDEXED)));
        UploadKnowledgeDocumentService service = new UploadKnowledgeDocumentService(
                storage, extractor, registration, documents, indexing, new KnowledgeFilePolicy());

        assertThatThrownBy(() -> service.upload(7L, 8L,
                new MockMultipartFile("file", "refund.md", "text/markdown", content)))
                .isInstanceOf(ConflictException.class)
                .hasMessage("该文档已存在,名称为 refund.md");

        verify(storage, never()).put(any(), any(), any(), any(), any(), any(), anyLong());
        verifyNoInteractions(registration);
    }
}
