package com.lqq.supportflow;

import static org.assertj.core.api.Assertions.assertThat;

import com.lqq.supportflow.analytics.OperationsMetricsService;
import javax.sql.DataSource;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.embedded.EmbeddedDatabaseBuilder;
import org.springframework.jdbc.datasource.embedded.EmbeddedDatabaseType;

class OperationsMetricsServiceTest {
    @Test
    void calculatesTenantScopedOperationsOverview() {
        DataSource dataSource = new EmbeddedDatabaseBuilder().setType(EmbeddedDatabaseType.H2)
                .addScript("classpath:db/migration/V1__identity_and_tenant.sql")
                .addScript("classpath:db/migration/V10__conversations_and_generations.sql")
                .addScript("classpath:db/migration/V11__tickets.sql")
                .addScript("classpath:db/migration/V17__generation_usage_metrics.sql").build();
        JdbcTemplate jdbc = new JdbcTemplate(dataSource);
        jdbc.update("INSERT INTO tenants VALUES (1, 'tenant', 'Tenant', 'ACTIVE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)");
        jdbc.update("INSERT INTO users VALUES (1, 'a@b.c', 'x', 'A', 'ACTIVE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)");
        jdbc.update("INSERT INTO conversations VALUES (10, 1, 1, 'OPEN', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)");
        jdbc.update("INSERT INTO conversation_messages VALUES (1, 1, 10, 'CUSTOMER', 'hello', NULL, NULL, CURRENT_TIMESTAMP)");
        jdbc.update("INSERT INTO generations(id, tenant_id, conversation_id, user_message_id, status, created_at, updated_at, input_tokens, output_tokens, latency_ms) VALUES (11, 1, 10, 1, 'COMPLETED', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 12, 34, 56)");
        jdbc.update("INSERT INTO generations(id, tenant_id, conversation_id, user_message_id, status, created_at, updated_at) VALUES (12, 1, 10, 1, 'HANDOFF_REQUIRED', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)");

        var overview = new OperationsMetricsService(jdbc).overview(1L);
        assertThat(overview.completedGenerations()).isEqualTo(1);
        assertThat(overview.handoffGenerations()).isEqualTo(1);
        assertThat(overview.aiResolutionRate()).isEqualTo(0.5);
        assertThat(overview.inputTokens()).isEqualTo(12);
        assertThat(overview.outputTokens()).isEqualTo(34);
        assertThat(overview.averageGenerationLatencyMs()).isEqualTo(56);
    }
}
