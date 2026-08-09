package com.lqq.supportflow.knowledge;

import com.lqq.supportflow.knowledge.application.SearchKnowledgeBaseService;
import com.lqq.supportflow.knowledge.domain.KnowledgeBasePort;
import java.util.Comparator;
import java.util.List;
import java.util.stream.IntStream;
import org.springframework.stereotype.Service;

@Service
public class KnowledgeRetrievalService {
    private final KnowledgeBasePort bases; private final SearchKnowledgeBaseService search;
    public KnowledgeRetrievalService(KnowledgeBasePort bases, SearchKnowledgeBaseService search) { this.bases = bases; this.search = search; }

    public List<RetrievedCitation> retrieve(Long tenantId, String query) {
        List<RetrievedCitation> citations = bases.list(tenantId).stream().flatMap(base -> {
            try { return search.search(tenantId, base.id(), query).citations().stream().map(citation -> new RetrievedCitation(base.id(), citation.documentId(), citation.chunkId(), citation.content(), citation.score(), citation.rank())); }
            catch (RuntimeException ignored) { return java.util.stream.Stream.empty(); }
        }).sorted(Comparator.comparingDouble(RetrievedCitation::score).reversed()).limit(6).toList();
        return IntStream.range(0, citations.size()).mapToObj(index -> {
            RetrievedCitation citation = citations.get(index);
            return new RetrievedCitation(citation.knowledgeBaseId(), citation.documentId(), citation.chunkId(), citation.content(), citation.score(), index + 1);
        }).toList();
    }
}
