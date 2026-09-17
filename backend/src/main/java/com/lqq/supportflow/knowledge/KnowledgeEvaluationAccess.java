package com.lqq.supportflow.knowledge;

import com.lqq.supportflow.knowledge.application.SearchKnowledgeBaseService;
import com.lqq.supportflow.knowledge.domain.KnowledgeBase;
import com.lqq.supportflow.knowledge.domain.KnowledgeBasePort;
import com.lqq.supportflow.knowledge.domain.KnowledgeCitation;
import com.lqq.supportflow.knowledge.domain.KnowledgeDocumentPort;
import java.util.List;
import org.springframework.stereotype.Service;

/** Public knowledge-module boundary used by the evaluation module. */
@Service
public class KnowledgeEvaluationAccess {
    private final KnowledgeBasePort bases;
    private final KnowledgeDocumentPort documents;
    private final SearchKnowledgeBaseService search;

    public KnowledgeEvaluationAccess(KnowledgeBasePort bases, KnowledgeDocumentPort documents, SearchKnowledgeBaseService search) {
        this.bases = bases;
        this.documents = documents;
        this.search = search;
    }

    public KnowledgeEvaluationContext context(Long tenantId, Long knowledgeBaseId) {
        KnowledgeBase base = bases.findById(tenantId, knowledgeBaseId).orElseThrow(() -> new IllegalArgumentException("knowledge base does not belong to tenant"));
        return new KnowledgeEvaluationContext(base.version());
    }

    public void requireDocument(Long tenantId, Long knowledgeBaseId, Long documentId) {
        documents.findById(tenantId, knowledgeBaseId, documentId).orElseThrow(() -> new IllegalArgumentException("expected document does not belong to knowledge base"));
    }

    public List<KnowledgeEvaluationCitation> retrieve(Long tenantId, Long knowledgeBaseId, String question) {
        return search.searchUntracked(tenantId, knowledgeBaseId, question).citations().stream()
                .map(citation -> new KnowledgeEvaluationCitation(citation.documentId(), citation.rank(), citation.score())).toList();
    }

    public record KnowledgeEvaluationContext(long knowledgeBaseVersion) { }
    public record KnowledgeEvaluationCitation(Long documentId, int rank, double score) { }
}
