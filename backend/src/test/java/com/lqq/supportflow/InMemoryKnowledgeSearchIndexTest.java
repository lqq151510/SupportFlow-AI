package com.lqq.supportflow;

import static org.assertj.core.api.Assertions.assertThat;

import com.lqq.supportflow.knowledge.domain.IndexedKnowledgeChunk;
import com.lqq.supportflow.knowledge.domain.KnowledgeChunk;
import com.lqq.supportflow.knowledge.domain.RankedKnowledgeChunk;
import com.lqq.supportflow.knowledge.infrastructure.search.InMemoryKnowledgeSearchIndex;
import java.util.List;
import org.junit.jupiter.api.Test;

class InMemoryKnowledgeSearchIndexTest {

    @Test
    void scopesKeywordAndVectorSearchesToTheKnowledgeBaseAndRanksResults() {
        InMemoryKnowledgeSearchIndex index = new InMemoryKnowledgeSearchIndex();
        index.index(7L, 8L, 10L, List.of(
                entry(1L, 10L, "Refund policy allows a refund within thirty days", new float[] {1F, 0F}),
                entry(2L, 10L, "Refund status and refund policy", new float[] {0.8F, 0.2F}),
                entry(3L, 10L, "Shipping status", new float[] {0F, 1F})));
        index.index(7L, 9L, 11L, List.of(entry(4L, 11L, "refund policy from another base", new float[] {1F, 0F})));
        index.index(6L, 8L, 12L, List.of(entry(5L, 12L, "refund policy from another tenant", new float[] {1F, 0F})));

        List<RankedKnowledgeChunk> keyword = index.keywordSearch(7L, 8L, "refund policy status", 2);
        assertThat(keyword).extracting(RankedKnowledgeChunk::chunkId).containsExactly(2L, 1L);
        assertThat(index.vectorSearch(7L, 8L, new float[] {1F, 0F}, 1))
                .extracting(RankedKnowledgeChunk::chunkId)
                .containsExactly(1L);
    }

    @Test
    void excludesBlankKeywordTermsAndReturnsZeroSimilarityForDegenerateVectors() {
        InMemoryKnowledgeSearchIndex index = new InMemoryKnowledgeSearchIndex();
        index.index(7L, 8L, 10L, List.of(
                entry(1L, 10L, "refund policy", new float[] {1F, 0F}),
                entry(2L, 10L, "another document", new float[] {0F, 0F})));

        assertThat(index.keywordSearch(7L, 8L, "   ", 10)).isEmpty();
        assertThat(index.vectorSearch(7L, 8L, new float[] {1F}, 10))
                .extracting(RankedKnowledgeChunk::score)
                .containsOnly(0D);
        assertThat(index.vectorSearch(7L, 8L, new float[] {0F, 0F}, 10))
                .extracting(RankedKnowledgeChunk::score)
                .containsOnly(0D);
    }

    private IndexedKnowledgeChunk entry(Long chunkId, Long documentId, String content, float[] embedding) {
        return new IndexedKnowledgeChunk(new KnowledgeChunk(chunkId, documentId, 0, content), embedding);
    }
}
