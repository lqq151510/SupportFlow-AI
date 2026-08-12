package com.lqq.supportflow.knowledge.application;

import com.lqq.supportflow.knowledge.domain.KnowledgeDocument;
import com.lqq.supportflow.knowledge.domain.KnowledgeDocumentPort;
import com.lqq.supportflow.model.MissingModelConfigurationException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

@Component
public class KnowledgeIndexingFailureHandler {
    static final String MODEL_NOT_CONFIGURED = "EMBEDDING_MODEL_NOT_CONFIGURED";
    static final String INDEXING_FAILED = "INDEXING_FAILED";

    private static final Logger log = LoggerFactory.getLogger(KnowledgeIndexingFailureHandler.class);

    private final KnowledgeDocumentPort documents;
    private final IndexKnowledgeDocumentService indexing;

    public KnowledgeIndexingFailureHandler(KnowledgeDocumentPort documents,
                                           IndexKnowledgeDocumentService indexing) {
        this.documents = documents;
        this.indexing = indexing;
    }

    public KnowledgeDocument index(Long tenantId, Long knowledgeBaseId, Long documentId) {
        try {
            return indexing.index(tenantId, knowledgeBaseId, documentId);
        } catch (RuntimeException exception) {
            String errorCode = exception instanceof MissingModelConfigurationException
                    ? MODEL_NOT_CONFIGURED
                    : INDEXING_FAILED;
            log.warn("Knowledge document indexing failed tenantId={} knowledgeBaseId={} documentId={} errorCode={} cause={}",
                    tenantId, knowledgeBaseId, documentId, errorCode,
                    exception.getClass().getSimpleName());
            return documents.markFailed(tenantId, documentId, errorCode);
        }
    }
}
