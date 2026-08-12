package com.lqq.supportflow;

import static org.assertj.core.api.Assertions.assertThat;

import com.lqq.supportflow.conversation.infrastructure.events.RedisGenerationEventStore;
import java.sql.DriverManager;
import java.time.Duration;
import org.junit.jupiter.api.Test;
import org.springframework.data.redis.connection.lettuce.LettuceConnectionFactory;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.testcontainers.containers.GenericContainer;
import org.testcontainers.containers.MySQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.utility.DockerImageName;

@Testcontainers(disabledWithoutDocker = true)
class InfrastructureContainerIntegrationTest {

    @Container
    static final MySQLContainer<?> mysql = new MySQLContainer<>("mysql:8.4")
            .withDatabaseName("supportflow_it")
            .withUsername("supportflow")
            .withPassword("supportflow");

    @Container
    static final GenericContainer<?> redis = new GenericContainer<>(DockerImageName.parse("redis:7.4-alpine"))
            .withExposedPorts(6379);

    @Test
    void mysqlAndRedisAdaptersUseRealContainersAndKeepTenantStreamsIsolated() throws Exception {
        try (var connection = DriverManager.getConnection(mysql.getJdbcUrl(), mysql.getUsername(), mysql.getPassword());
                var statement = connection.createStatement();
                var result = statement.executeQuery("SELECT 1")) {
            assertThat(result.next()).isTrue();
            assertThat(result.getInt(1)).isEqualTo(1);
        }

        LettuceConnectionFactory connectionFactory = new LettuceConnectionFactory(redis.getHost(), redis.getMappedPort(6379));
        connectionFactory.afterPropertiesSet();
        try {
            StringRedisTemplate template = new StringRedisTemplate(connectionFactory);
            template.afterPropertiesSet();
            RedisGenerationEventStore events = new RedisGenerationEventStore(template, Duration.ofMinutes(10));

            events.append(1L, 99L, "text.delta", "{\"text\":\"first\"}");
            events.appendIfAbsent(1L, 99L, "handoff.required", "{\"reason\":\"policy\"}");
            events.appendIfAbsent(1L, 99L, "handoff.required", "{\"reason\":\"duplicate\"}");
            events.append(2L, 99L, "text.delta", "{\"text\":\"other tenant\"}");

            assertThat(events.readAfter(1L, 99L, null))
                    .extracting(event -> event.type() + ":" + event.data())
                    .containsExactly("text.delta:{\"text\":\"first\"}", "handoff.required:{\"reason\":\"policy\"}");
            assertThat(events.readAfter(2L, 99L, null))
                    .extracting(event -> event.type() + ":" + event.data())
                    .containsExactly("text.delta:{\"text\":\"other tenant\"}");
        } finally {
            connectionFactory.destroy();
        }
    }
}
