package com.lqq.supportflow.knowledge;

import com.lqq.supportflow.knowledge.application.SearchKnowledgeBaseService;
import com.lqq.supportflow.knowledge.domain.KnowledgeBasePort;
import java.util.Comparator;
import java.util.List;
import java.util.stream.IntStream;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

@Service
public class KnowledgeRetrievalService {
    private final KnowledgeBasePort bases; private final SearchKnowledgeBaseService search; private final double minimumScore; private final int minimumCitations;
    public KnowledgeRetrievalService(KnowledgeBasePort bases, SearchKnowledgeBaseService search, @Value("${supportflow.knowledge.retrieval.minimum-score:0.0}") double minimumScore, @Value("${supportflow.knowledge.retrieval.minimum-citations:1}") int minimumCitations) { this.bases = bases; this.search = search; this.minimumScore = minimumScore; this.minimumCitations = minimumCitations; }

    public List<RetrievedCitation> retrieve(Long tenantId, String query) {
        List<RetrievedCitation> citations = bases.list(tenantId).stream().flatMap(base -> {
            try { return search.search(tenantId, base.id(), query).citations().stream().map(citation -> new RetrievedCitation(base.id(), citation.documentId(), citation.chunkId(), citation.content(), citation.score(), citation.rank())); }
            catch (RuntimeException ignored) { return java.util.stream.Stream.empty(); }
        }).filter(citation -> citation.score() >= minimumScore).sorted(Comparator.comparingDouble(RetrievedCitation::score).reversed()).limit(6).toList();
        if (citations.size() < minimumCitations) return List.of();
        return IntStream.range(0, citations.size()).mapToObj(index -> {
            RetrievedCitation citation = citations.get(index);
            return new RetrievedCitation(citation.knowledgeBaseId(), citation.documentId(), citation.chunkId(), citation.content(), citation.score(), index + 1);
        }).toList();
    }
}
