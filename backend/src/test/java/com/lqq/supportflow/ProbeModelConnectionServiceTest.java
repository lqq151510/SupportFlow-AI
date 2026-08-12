package com.lqq.supportflow;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.lqq.supportflow.model.application.ProbeModelConnectionService;
import com.lqq.supportflow.model.domain.ModelUrlPolicy;
import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.Test;
import org.springframework.web.reactive.function.client.WebClient;

class ProbeModelConnectionServiceTest {

    @Test
    void reportsHttpStatusAndSendsBearerCredentials() throws Exception {
        AtomicReference<String> authorization = new AtomicReference<>();
        HttpServer server = server(exchange -> {
            authorization.set(exchange.getRequestHeaders().getFirst("Authorization"));
            exchange.sendResponseHeaders(401, -1);
            exchange.close();
        });
        try {
            ProbeModelConnectionService.ProbeResult result = service().probe(url(server), "test-key");
            assertThat(result).isEqualTo(new ProbeModelConnectionService.ProbeResult(true, "HTTP 401"));
            assertThat(authorization.get()).isEqualTo("Bearer test-key");
        } finally {
            server.stop(0);
        }
    }

    @Test
    void treatsServerErrorsAndConnectionFailuresAsUnreachable() throws Exception {
        HttpServer server = server(exchange -> {
            exchange.sendResponseHeaders(503, -1);
            exchange.close();
        });
        try {
            assertThat(service().probe(url(server), "key")).isEqualTo(new ProbeModelConnectionService.ProbeResult(false, "HTTP 503"));
        } finally {
            server.stop(0);
        }
        assertThat(service().probe("http://127.0.0.1:1", "key"))
                .isEqualTo(new ProbeModelConnectionService.ProbeResult(false, "connection failed"));
    }

    @Test
    void validatesTheTargetBeforeMakingAnyRequest() {
        ModelUrlPolicy rejecting = value -> { throw new IllegalArgumentException("private target"); };
        ProbeModelConnectionService service = new ProbeModelConnectionService(rejecting, WebClient.builder());
        assertThatThrownBy(() -> service.probe("https://invalid.example", "key"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("private target");
    }

    private ProbeModelConnectionService service() {
        return new ProbeModelConnectionService(value -> { }, WebClient.builder());
    }

    private String url(HttpServer server) {
        return "http://localhost:" + server.getAddress().getPort();
    }

    private HttpServer server(com.sun.net.httpserver.HttpHandler handler) throws Exception {
        HttpServer server = HttpServer.create(new InetSocketAddress(0), 0);
        server.createContext("/", handler);
        server.start();
        return server;
    }
}
