package com.lqq.supportflow;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.lqq.supportflow.model.domain.ChatModelConfig;
import com.lqq.supportflow.model.domain.ChatModelRequest;
import com.lqq.supportflow.model.domain.ModelConfigPort;
import com.lqq.supportflow.model.domain.ModelEvent;
import com.lqq.supportflow.model.domain.ModelProtocol;
import com.lqq.supportflow.model.domain.ModelSecretPort;
import com.lqq.supportflow.model.infrastructure.protocol.AnthropicMessagesEventNormalizer;
import com.lqq.supportflow.model.infrastructure.protocol.ConfiguredChatModelGateway;
import com.lqq.supportflow.model.infrastructure.protocol.OpenAiCompatibleEventNormalizer;
import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Optional;
import java.util.concurrent.atomic.AtomicReference;
import java.time.Duration;
import org.junit.jupiter.api.Test;
import org.springframework.web.reactive.function.client.WebClient;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class ConfiguredChatModelGatewayHttpTest {
    @Test
    void sendsOpenAiCompatibleSseRequestAndNormalizesResponse() throws Exception {
        AtomicReference<String> authorization = new AtomicReference<>();
        AtomicReference<String> requestPath = new AtomicReference<>();
        HttpServer server = server(exchange -> {
            authorization.set(exchange.getRequestHeaders().getFirst("Authorization"));
            requestPath.set(exchange.getRequestURI().getPath());
            byte[] body = "data: {\"choices\":[{\"delta\":{\"content\":\"hello\"}}]}\n\ndata: [DONE]\n\n".getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().add("Content-Type", "text/event-stream"); exchange.sendResponseHeaders(200, body.length); exchange.getResponseBody().write(body); exchange.close();
        });
        try {
            List<ModelEvent> events = gateway(server, ModelProtocol.OPENAI_COMPATIBLE).stream(request()).collectList().block();
            assertThat(requestPath.get()).isEqualTo("/chat/completions");
            assertThat(authorization.get()).isEqualTo("Bearer decrypted-key");
            assertThat(events).containsExactly(new ModelEvent.TextDelta("hello"), new ModelEvent.ModelCompleted());
        } finally { server.stop(0); }
    }

    @Test
    void sendsAnthropicHeadersAndNormalizesTypedSseEvents() throws Exception {
        AtomicReference<String> apiKey = new AtomicReference<>();
        HttpServer server = server(exchange -> {
            apiKey.set(exchange.getRequestHeaders().getFirst("x-api-key"));
            byte[] body = "event: content_block_delta\ndata: {\"delta\":{\"text\":\"hello\"}}\n\nevent: message_stop\ndata: {}\n\n".getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().add("Content-Type", "text/event-stream"); exchange.sendResponseHeaders(200, body.length); exchange.getResponseBody().write(body); exchange.close();
        });
        try {
            List<ModelEvent> events = gateway(server, ModelProtocol.ANTHROPIC_MESSAGES).stream(request()).collectList().block();
            assertThat(apiKey.get()).isEqualTo("decrypted-key");
            assertThat(events).containsExactly(new ModelEvent.TextDelta("hello"), new ModelEvent.ModelCompleted());
        } finally { server.stop(0); }
    }

    @Test
    void propagatesServerErrorsAndTimesOutStalledStreams() throws Exception {
        HttpServer failed = server(exchange -> { exchange.sendResponseHeaders(503, -1); exchange.close(); });
        try {
            assertThatThrownBy(() -> gateway(failed, ModelProtocol.OPENAI_COMPATIBLE, Duration.ofSeconds(5))
                    .stream(request()).collectList().block())
                    .isInstanceOf(org.springframework.web.reactive.function.client.WebClientResponseException.ServiceUnavailable.class);
        } finally { failed.stop(0); }

        HttpServer stalled = server(exchange -> {
            try { Thread.sleep(250); } catch (InterruptedException interrupted) { Thread.currentThread().interrupt(); }
            exchange.sendResponseHeaders(200, -1); exchange.close();
        });
        try {
            assertThatThrownBy(() -> gateway(stalled, ModelProtocol.ANTHROPIC_MESSAGES, Duration.ofMillis(30))
                    .stream(request()).collectList().block())
                    .hasRootCauseInstanceOf(java.util.concurrent.TimeoutException.class);
        } finally { stalled.stop(0); }
    }

    private ConfiguredChatModelGateway gateway(HttpServer server, ModelProtocol protocol) {
        return gateway(server, protocol, Duration.ofSeconds(5));
    }

    private ConfiguredChatModelGateway gateway(HttpServer server, ModelProtocol protocol, Duration timeout) {
        ModelConfigPort configs = mock(ModelConfigPort.class); ModelSecretPort secrets = mock(ModelSecretPort.class);
        when(configs.findDefaultChat(7L)).thenReturn(Optional.of(new ChatModelConfig(protocol, "http://localhost:" + server.getAddress().getPort(), "test-model", "encrypted")));
        when(secrets.decrypt("encrypted")).thenReturn("decrypted-key");
        ObjectMapper json = new ObjectMapper();
        return new ConfiguredChatModelGateway(configs, secrets, WebClient.builder(), new OpenAiCompatibleEventNormalizer(json), new AnthropicMessagesEventNormalizer(json), timeout);
    }

    private ChatModelRequest request() { return new ChatModelRequest(7L, List.of(new ChatModelRequest.ChatMessage("user", "hello")), List.of()); }
    private HttpServer server(com.sun.net.httpserver.HttpHandler handler) throws Exception { HttpServer server = HttpServer.create(new InetSocketAddress(0), 0); server.createContext("/", handler); server.start(); return server; }
}
