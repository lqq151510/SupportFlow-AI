package com.lqq.supportflow;

import static org.assertj.core.api.Assertions.assertThat;

import com.lqq.supportflow.knowledge.domain.IndexedKnowledgeChunk;
import com.lqq.supportflow.knowledge.domain.KnowledgeChunk;
import com.lqq.supportflow.knowledge.infrastructure.search.ElasticsearchKnowledgeSearchIndex;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;
import org.springframework.web.reactive.function.client.WebClient;
import org.testcontainers.elasticsearch.ElasticsearchContainer;
import org.testcontainers.containers.wait.strategy.Wait;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

@Testcontainers(disabledWithoutDocker = true)
class ElasticsearchContainerIntegrationTest {

    @Container
    static final ElasticsearchContainer elasticsearch = new ElasticsearchContainer(
            "docker.elastic.co/elasticsearch/elasticsearch:8.17.3")
            .withEnv("xpack.security.enabled", "false")
            .withEnv("ES_JAVA_OPTS", "-Xms384m -Xmx384m")
            .waitingFor(Wait.forHttp("/").forStatusCode(200)
                    .withStartupTimeout(Duration.ofMinutes(2)));

    @Test
    @Timeout(value = 2, unit = java.util.concurrent.TimeUnit.MINUTES)
    void indexesAndSearchesRealElasticsearchWithoutCrossTenantResults() throws Exception {
        String endpoint = "http://" + elasticsearch.getHttpHostAddress();
        String indexName = "supportflow-knowledge-it";
        request(endpoint + "/" + indexName, "PUT", """
                {
                  "mappings": {
                    "properties": {
                      "tenantId": {"type": "long"},
                      "knowledgeBaseId": {"type": "long"},
                      "documentId": {"type": "long"},
                      "chunkId": {"type": "long"},
                      "content": {"type": "text"},
                      "embedding": {"type": "dense_vector", "dims": 2, "index": true, "similarity": "cosine"}
                    }
                  }
                }
                """);

        ElasticsearchKnowledgeSearchIndex searchIndex = new ElasticsearchKnowledgeSearchIndex(
                WebClient.builder(), endpoint, indexName);
        searchIndex.index(7L, 8L, 10L, List.of(
                new IndexedKnowledgeChunk(
                        new KnowledgeChunk(31L, 10L, 0, "refund policy allows returns"),
                        new float[] {1F, 0F})));
        request(endpoint + "/" + indexName + "/_refresh", "POST", "");

        assertThat(searchIndex.keywordSearch(7L, 8L, "refund", 3))
                .singleElement()
                .satisfies(hit -> {
                    assertThat(hit.chunkId()).isEqualTo(31L);
                    assertThat(hit.documentId()).isEqualTo(10L);
                    assertThat(hit.content()).contains("refund policy");
                });
        assertThat(searchIndex.vectorSearch(7L, 8L, new float[] {1F, 0F}, 3))
                .extracting(hit -> hit.chunkId())
                .containsExactly(31L);
        assertThat(searchIndex.keywordSearch(99L, 8L, "refund", 3)).isEmpty();
    }

    private void request(String uri, String method, String body) throws Exception {
        HttpRequest request = HttpRequest.newBuilder(URI.create(uri))
                .header("Content-Type", "application/json")
                .method(method, HttpRequest.BodyPublishers.ofString(body))
                .build();
        HttpResponse<String> response = HttpClient.newHttpClient().send(request, HttpResponse.BodyHandlers.ofString());
        assertThat(response.statusCode())
                .withFailMessage("Elasticsearch returned %s: %s%nContainer logs:%n%s",
                        response.statusCode(), response.body(), elasticsearch.getLogs())
                .isBetween(200, 299);
    }
}
