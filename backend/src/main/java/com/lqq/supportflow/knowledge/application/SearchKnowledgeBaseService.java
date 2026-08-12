package com.lqq.supportflow.knowledge.application;

import com.lqq.supportflow.knowledge.domain.KnowledgeBase;
import com.lqq.supportflow.knowledge.domain.KnowledgeBasePort;
import com.lqq.supportflow.knowledge.domain.KnowledgeCitation;
import com.lqq.supportflow.knowledge.domain.KnowledgeSearchAuditPort;
import com.lqq.supportflow.knowledge.domain.KnowledgeSearchIndex;
import com.lqq.supportflow.knowledge.domain.KnowledgeSearchResult;
import com.lqq.supportflow.knowledge.domain.RankedKnowledgeChunk;
import com.lqq.supportflow.model.ModelEmbeddingService;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

@Service
public class SearchKnowledgeBaseService {
    private static final int CANDIDATE_LIMIT = 20;
    private static final int RESULT_LIMIT = 6;
    private static final int RRF_K = 60;

    private final KnowledgeBasePort bases;
    private final KnowledgeSearchIndex index;
    private final ModelEmbeddingService embeddings;
    private final KnowledgeSearchAuditPort audits;
    private final double minimumRrfScore;

    public SearchKnowledgeBaseService(KnowledgeBasePort bases, KnowledgeSearchIndex index,
                                      ModelEmbeddingService embeddings, KnowledgeSearchAuditPort audits,
                                      @Value("${supportflow.knowledge.search.minimum-rrf-score:0.015}") double minimumRrfScore) {
        if (minimumRrfScore < 0.0) throw new IllegalArgumentException("minimum RRF score cannot be negative");
        this.bases = bases;
        this.index = index;
        this.embeddings = embeddings;
        this.audits = audits;
        this.minimumRrfScore = minimumRrfScore;
    }

    public KnowledgeSearchResult search(Long tenantId, Long knowledgeBaseId, String query) {
        KnowledgeBase knowledgeBase = bases.findById(tenantId, knowledgeBaseId)
                .orElseThrow(() -> new IllegalArgumentException("knowledge base does not belong to tenant"));
        List<RankedKnowledgeChunk> keyword = index.keywordSearch(tenantId, knowledgeBaseId, query, CANDIDATE_LIMIT);
        List<float[]> vectors = embeddings.embed(tenantId, List.of(query));
        if (vectors.size() != 1) throw new IllegalArgumentException("query embedding is invalid");
        List<RankedKnowledgeChunk> dense = index.vectorSearch(tenantId, knowledgeBaseId, vectors.getFirst(), CANDIDATE_LIMIT);
        Map<Long, Candidate> combined = new HashMap<>();
        merge(combined, keyword);
        merge(combined, dense);
        List<Candidate> selected = combined.values().stream()
                .sorted(Comparator.comparingDouble(Candidate::score).reversed())
                .filter(candidate -> candidate.score >= minimumRrfScore)
                .limit(RESULT_LIMIT)
                .toList();
        List<KnowledgeCitation> citations = new ArrayList<>();
        for (int position = 0; position < selected.size(); position++) {
            Candidate candidate = selected.get(position);
            citations.add(new KnowledgeCitation(candidate.chunk.chunkId(), candidate.chunk.documentId(),
                    candidate.chunk.content(), candidate.score, position + 1));
        }
        return new KnowledgeSearchResult(
                audits.save(tenantId, knowledgeBaseId, knowledgeBase.version(), query, citations), citations);
    }

    private void merge(Map<Long, Candidate> combined, List<RankedKnowledgeChunk> results) {
        for (int position = 0; position < results.size(); position++) {
            RankedKnowledgeChunk chunk = results.get(position);
            Candidate candidate = combined.computeIfAbsent(chunk.chunkId(), ignored -> new Candidate(chunk));
            candidate.score += 1.0 / (RRF_K + position + 1);
        }
    }

    private static final class Candidate {
        private final RankedKnowledgeChunk chunk;
        private double score;
        private Candidate(RankedKnowledgeChunk chunk) { this.chunk = chunk; }
        private double score() { return score; }
    }
}
