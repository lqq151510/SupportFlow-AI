package com.lqq.supportflow.analytics;

import java.sql.Timestamp;
import java.time.Instant;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

@Service
public class OperationsMetricsService {
    private final JdbcTemplate jdbc;

    public OperationsMetricsService(JdbcTemplate jdbc) { this.jdbc = jdbc; }

    public OperationsOverview overview(Long tenantId) {
        long completed = count("SELECT COUNT(*) FROM generations WHERE tenant_id = ? AND status = 'COMPLETED'", tenantId);
        long handoff = count("SELECT COUNT(*) FROM generations WHERE tenant_id = ? AND status = 'HANDOFF_REQUIRED'", tenantId);
        long overdue = count("SELECT COUNT(*) FROM tickets WHERE tenant_id = ? AND resolution_due_at <= ? AND status NOT IN ('RESOLVED', 'CLOSED')", tenantId, Timestamp.from(Instant.now()));
        long input = value("SELECT COALESCE(SUM(input_tokens), 0) FROM generations WHERE tenant_id = ?", tenantId);
        long output = value("SELECT COALESCE(SUM(output_tokens), 0) FROM generations WHERE tenant_id = ?", tenantId);
        long latency = value("SELECT COALESCE(AVG(latency_ms), 0) FROM generations WHERE tenant_id = ? AND latency_ms IS NOT NULL", tenantId);
        long terminal = completed + handoff;
        return new OperationsOverview(completed, handoff, terminal == 0 ? 0.0 : (double) completed / terminal, overdue, input, output, latency);
    }

    private long count(String sql, Object... values) { return value(sql, values); }
    private long value(String sql, Object... values) { Number value = jdbc.queryForObject(sql, Number.class, values); return value == null ? 0L : value.longValue(); }
}
