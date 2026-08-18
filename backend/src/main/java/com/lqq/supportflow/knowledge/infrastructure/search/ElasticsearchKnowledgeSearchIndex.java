package com.lqq.supportflow.knowledge.infrastructure.search;

import com.fasterxml.jackson.databind.JsonNode;
import com.lqq.supportflow.knowledge.domain.IndexedKnowledgeChunk;
import com.lqq.supportflow.knowledge.domain.KnowledgeChunk;
import com.lqq.supportflow.knowledge.domain.KnowledgeSearchIndex;
import com.lqq.supportflow.knowledge.domain.RankedKnowledgeChunk;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;

@Component
@ConditionalOnProperty(prefix = "supportflow.search.elasticsearch", name = "enabled", havingValue = "true")
public class ElasticsearchKnowledgeSearchIndex implements KnowledgeSearchIndex {

    private final WebClient client;
    private final String index;

    public ElasticsearchKnowledgeSearchIndex(WebClient.Builder builder,
                                             @Value("${supportflow.search.elasticsearch.endpoint}") String endpoint,
                                             @Value("${supportflow.search.elasticsearch.index:supportflow-knowledge}") String index) {
        this.client = builder.baseUrl(endpoint).build();
        this.index = index;
    }

    @Override
    public void index(Long tenantId, Long knowledgeBaseId, Long documentId, List<IndexedKnowledgeChunk> entries) {
        for (IndexedKnowledgeChunk entry : entries) {
            KnowledgeChunk chunk = entry.chunk();
            List<Float> vector = new ArrayList<>();
            for (float value : entry.embedding()) vector.add(value);
            Map<String, Object> document = Map.of(
                    "tenantId", tenantId,
                    "knowledgeBaseId", knowledgeBaseId,
                    "documentId", documentId,
                    "chunkId", chunk.id(),
                    "chunkNo", chunk.chunkNo(),
                    "content", chunk.content(),
                    "embedding", vector);
            try {
                client.put().uri("/" + index + "/_doc/" + chunk.id()).bodyValue(document).retrieve().toBodilessEntity().block(Duration.ofSeconds(15));
            } catch (WebClientResponseException.NotFound notFound) {
                initIndex(entry.embedding().length);
                client.put().uri("/" + index + "/_doc/" + chunk.id()).bodyValue(document).retrieve().toBodilessEntity().block(Duration.ofSeconds(15));
            }
        }
    }

    @Override
    public List<RankedKnowledgeChunk> keywordSearch(Long tenantId, Long knowledgeBaseId, String query, int limit) {
        return search(Map.of(
                "size", limit,
                "query", Map.of("bool", Map.of("must", List.of(Map.of("match", Map.of("content", query))), "filter", filters(tenantId, knowledgeBaseId)))));
    }

    @Override
    public List<RankedKnowledgeChunk> vectorSearch(Long tenantId, Long knowledgeBaseId, float[] vector, int limit) {
        List<Float> values = new ArrayList<>();
        for (float value : vector) values.add(value);
        return search(Map.of(
                "size", limit,
                "knn", Map.of("field", "embedding", "query_vector", values, "k", limit, "num_candidates", Math.max(100, limit), "filter", filters(tenantId, knowledgeBaseId))));
    }

    private void initIndex(int dims) {
        try {
            Map<String, Object> mapping = Map.of(
                    "mappings", Map.of(
                            "properties", Map.of(
                                    "tenantId", Map.of("type", "long"),
                                    "knowledgeBaseId", Map.of("type", "long"),
                                    "documentId", Map.of("type", "long"),
                                    "chunkId", Map.of("type", "long"),
                                    "chunkNo", Map.of("type", "integer"),
                                    "content", Map.of("type", "text"),
                                    "embedding", Map.of("type", "dense_vector", "dims", dims, "index", true, "similarity", "cosine")
                            )
                    )
            );
            client.put().uri("/" + index).bodyValue(mapping).retrieve().toBodilessEntity().block(Duration.ofSeconds(10));
        } catch (Exception ignored) {
        }
    }

    private List<Map<String, Object>> filters(Long tenantId, Long knowledgeBaseId) {
        return List.of(Map.of("term", Map.of("tenantId", tenantId)), Map.of("term", Map.of("knowledgeBaseId", knowledgeBaseId)));
    }

    private List<RankedKnowledgeChunk> search(Map<String, Object> body) {
        JsonNode response = client.post().uri("/" + index + "/_search").bodyValue(body).retrieve().bodyToMono(JsonNode.class).block(Duration.ofSeconds(15));
        if (response == null) return List.of();
        List<RankedKnowledgeChunk> results = new ArrayList<>();
        for (JsonNode hit : response.path("hits").path("hits")) {
            JsonNode source = hit.path("_source");
            results.add(new RankedKnowledgeChunk(source.path("chunkId").asLong(), source.path("documentId").asLong(), source.path("content").asText(), hit.path("_score").asDouble()));
        }
        return results;
    }
}
