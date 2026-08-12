package com.lqq.supportflow.knowledge.application;

import com.lqq.supportflow.knowledge.domain.IngestionStatus;
import com.lqq.supportflow.knowledge.domain.KnowledgeDocument;
import com.lqq.supportflow.knowledge.domain.KnowledgeDocumentPort;
import org.springframework.stereotype.Service;

@Service
public class RetryKnowledgeDocumentService {
    private final KnowledgeDocumentPort documents;
    private final KnowledgeIndexingFailureHandler indexing;

    public RetryKnowledgeDocumentService(KnowledgeDocumentPort documents,
                                         KnowledgeIndexingFailureHandler indexing) {
        this.documents = documents;
        this.indexing = indexing;
    }

    public KnowledgeDocument retry(Long tenantId, Long knowledgeBaseId, Long documentId) {
        KnowledgeDocument document = documents.findById(tenantId, knowledgeBaseId, documentId)
                .orElseThrow(() -> new IllegalArgumentException("document does not belong to tenant"));
        if (document.status() == IngestionStatus.FAILED) {
            document = documents.transitionStatus(tenantId, documentId,
                    IngestionStatus.FAILED, IngestionStatus.PARSING);
            document = documents.transitionStatus(tenantId, documentId,
                    IngestionStatus.PARSING, IngestionStatus.CHUNKING);
            document = documents.transitionStatus(tenantId, documentId,
                    IngestionStatus.CHUNKING, IngestionStatus.EMBEDDING);
        }
        if (document.status() != IngestionStatus.EMBEDDING) {
            throw new IllegalArgumentException("document is not retryable");
        }
        return indexing.index(tenantId, knowledgeBaseId, documentId);
    }
}
