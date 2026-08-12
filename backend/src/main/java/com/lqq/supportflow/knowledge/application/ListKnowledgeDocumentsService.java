package com.lqq.supportflow.knowledge.application;

import com.lqq.supportflow.knowledge.domain.KnowledgeBasePort;
import com.lqq.supportflow.knowledge.domain.KnowledgeDocument;
import com.lqq.supportflow.knowledge.domain.KnowledgeDocumentPort;
import java.util.List;
import org.springframework.stereotype.Service;

@Service
public class ListKnowledgeDocumentsService {
    private final KnowledgeBasePort knowledgeBases;
    private final KnowledgeDocumentPort documents;

    public ListKnowledgeDocumentsService(KnowledgeBasePort knowledgeBases, KnowledgeDocumentPort documents) {
        this.knowledgeBases = knowledgeBases;
        this.documents = documents;
    }

    public List<KnowledgeDocument> list(Long tenantId, Long knowledgeBaseId) {
        if (!knowledgeBases.belongsTo(tenantId, knowledgeBaseId)) {
            throw new IllegalArgumentException("knowledge base does not belong to tenant");
        }
        return documents.findByKnowledgeBase(tenantId, knowledgeBaseId);
    }
}
