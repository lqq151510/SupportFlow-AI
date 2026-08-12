package com.lqq.supportflow;

import static org.assertj.core.api.Assertions.assertThat;

import com.lqq.supportflow.knowledge.domain.IndexedKnowledgeChunk;
import com.lqq.supportflow.knowledge.domain.KnowledgeChunk;
import com.lqq.supportflow.knowledge.domain.RankedKnowledgeChunk;
import com.lqq.supportflow.knowledge.infrastructure.search.ElasticsearchKnowledgeSearchIndex;
import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;
import org.junit.jupiter.api.Test;
import org.springframework.web.reactive.function.client.WebClient;

class ElasticsearchKnowledgeSearchIndexHttpTest {

    @Test
    void indexesChunksAndQueriesTenantScopedKeywordAndVectorResults() throws Exception {
        List<String> paths = new CopyOnWriteArrayList<>();
        List<String> bodies = new CopyOnWriteArrayList<>();
        HttpServer server = server(exchange -> {
            paths.add(exchange.getRequestURI().getPath());
            bodies.add(new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8));
            if (exchange.getRequestURI().getPath().endsWith("_search")) {
                byte[] result = "{\"hits\":{\"hits\":[{\"_score\":0.9,\"_source\":{\"chunkId\":31,\"documentId\":10,\"content\":\"refund policy\"}}]}}".getBytes(StandardCharsets.UTF_8);
                exchange.getResponseHeaders().add("Content-Type", "application/json");
                exchange.sendResponseHeaders(200, result.length);
                exchange.getResponseBody().write(result);
            } else {
                exchange.sendResponseHeaders(201, -1);
            }
            exchange.close();
        });
        try {
            ElasticsearchKnowledgeSearchIndex index = index(server);
            index.index(7L, 8L, 10L, List.of(new IndexedKnowledgeChunk(new KnowledgeChunk(31L, 10L, 0, "refund policy"), new float[] {1F, 2F})));
            assertThat(index.keywordSearch(7L, 8L, "refund", 3))
                    .containsExactly(new RankedKnowledgeChunk(31L, 10L, "refund policy", 0.9));
            assertThat(index.vectorSearch(7L, 8L, new float[] {1F, 2F}, 3))
                    .containsExactly(new RankedKnowledgeChunk(31L, 10L, "refund policy", 0.9));
            assertThat(paths).containsExactly("/knowledge/_doc/31", "/knowledge/_search", "/knowledge/_search");
            assertThat(bodies.getFirst()).contains("\"tenantId\":7", "\"embedding\":[1.0,2.0]");
            assertThat(bodies.get(1)).contains("\"match\"", "\"knowledgeBaseId\":8");
            assertThat(bodies.get(2)).contains("\"knn\"", "\"query_vector\":[1.0,2.0]");
        } finally {
            server.stop(0);
        }
    }

    @Test
    void returnsNoResultsForAnEmptyElasticsearchHitList() throws Exception {
        HttpServer server = server(exchange -> {
            byte[] result = "{\"hits\":{\"hits\":[]}}".getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().add("Content-Type", "application/json");
            exchange.sendResponseHeaders(200, result.length);
            exchange.getResponseBody().write(result);
            exchange.close();
        });
        try {
            assertThat(index(server).keywordSearch(7L, 8L, "refund", 3)).isEmpty();
        } finally {
            server.stop(0);
        }
    }

    private ElasticsearchKnowledgeSearchIndex index(HttpServer server) {
        return new ElasticsearchKnowledgeSearchIndex(WebClient.builder(), "http://localhost:" + server.getAddress().getPort(), "knowledge");
    }

    private HttpServer server(com.sun.net.httpserver.HttpHandler handler) throws Exception {
        HttpServer server = HttpServer.create(new InetSocketAddress(0), 0);
        server.createContext("/", handler);
        server.start();
        return server;
    }
}
