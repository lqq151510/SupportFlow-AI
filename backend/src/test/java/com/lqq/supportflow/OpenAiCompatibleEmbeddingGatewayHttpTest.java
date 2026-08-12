package com.lqq.supportflow;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import com.lqq.supportflow.model.domain.EmbeddingModelConfig;
import com.lqq.supportflow.model.MissingModelConfigurationException;
import com.lqq.supportflow.model.domain.EmbeddingRequest;
import com.lqq.supportflow.model.domain.ModelConfigPort;
import com.lqq.supportflow.model.domain.ModelSecretPort;
import com.lqq.supportflow.model.infrastructure.protocol.OpenAiCompatibleEmbeddingGateway;
import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Optional;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.Test;
import org.springframework.web.reactive.function.client.WebClient;

class OpenAiCompatibleEmbeddingGatewayHttpTest {

    @Test
    void callsTheEmbeddingEndpointAndPreservesVectorOrder() throws Exception {
        AtomicReference<String> authorization = new AtomicReference<>();
        AtomicReference<String> path = new AtomicReference<>();
        HttpServer server = server(exchange -> {
            authorization.set(exchange.getRequestHeaders().getFirst("Authorization"));
            path.set(exchange.getRequestURI().getPath());
            byte[] body = "{\"data\":[{\"embedding\":[1.5,2.0]},{\"embedding\":[3.0]}]}".getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().add("Content-Type", "application/json");
            exchange.sendResponseHeaders(200, body.length);
            exchange.getResponseBody().write(body);
            exchange.close();
        });
        try {
            List<float[]> vectors = gateway(server, Optional.of(config(server))).embedBatch(new EmbeddingRequest(7L, List.of("first", "second")));
            assertThat(path.get()).isEqualTo("/v1/embeddings");
            assertThat(authorization.get()).isEqualTo("Bearer decrypted-key");
            assertThat(vectors).containsExactly(new float[] {1.5F, 2.0F}, new float[] {3.0F});
        } finally {
            server.stop(0);
        }
    }

    @Test
    void rejectsMissingDefaultInvalidPayloadAndMismatchedVectorCount() throws Exception {
        ModelConfigPort configs = mock(ModelConfigPort.class);
        OpenAiCompatibleEmbeddingGateway absent = gateway(null, Optional.empty(), configs);
        assertThatThrownBy(() -> absent.embedBatch(new EmbeddingRequest(7L, List.of("one"))))
                .isInstanceOf(MissingModelConfigurationException.class)
                .hasMessage("default OpenAI-compatible embedding model is not configured");

        assertInvalidResponse("{}", "embedding response is invalid");
        assertInvalidResponse("{\"data\":[{\"embedding\":[1.0]}]}", "embedding response count does not match input count");
    }

    private void assertInvalidResponse(String response, String message) throws Exception {
        HttpServer server = server(exchange -> {
            byte[] body = response.getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().add("Content-Type", "application/json");
            exchange.sendResponseHeaders(200, body.length);
            exchange.getResponseBody().write(body);
            exchange.close();
        });
        try {
            assertThatThrownBy(() -> gateway(server, Optional.of(config(server))).embedBatch(new EmbeddingRequest(7L, List.of("one", "two"))))
                    .isInstanceOf(IllegalArgumentException.class)
                    .hasMessage(message);
        } finally {
            server.stop(0);
        }
    }

    private OpenAiCompatibleEmbeddingGateway gateway(HttpServer server, Optional<EmbeddingModelConfig> config) {
        return gateway(server, config, mock(ModelConfigPort.class));
    }

    private OpenAiCompatibleEmbeddingGateway gateway(HttpServer server, Optional<EmbeddingModelConfig> config, ModelConfigPort configs) {
        when(configs.findDefaultEmbedding(7L)).thenReturn(config);
        ModelSecretPort secrets = mock(ModelSecretPort.class);
        when(secrets.decrypt("encrypted")).thenReturn("decrypted-key");
        return new OpenAiCompatibleEmbeddingGateway(configs, secrets, WebClient.builder());
    }

    private EmbeddingModelConfig config(HttpServer server) {
        return new EmbeddingModelConfig("http://localhost:" + server.getAddress().getPort() + "/v1/", "embedding-model", "encrypted");
    }

    private HttpServer server(com.sun.net.httpserver.HttpHandler handler) throws Exception {
        HttpServer server = HttpServer.create(new InetSocketAddress(0), 0);
        server.createContext("/", handler);
        server.start();
        return server;
    }
}
