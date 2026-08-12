package com.lqq.supportflow;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.doThrow;

import com.lqq.supportflow.eventing.OutboxService;
import com.lqq.supportflow.shared.AuthenticatedPrincipal;
import com.lqq.supportflow.shared.TenantContext;
import com.lqq.supportflow.ticket.SlaDeadline;
import com.lqq.supportflow.ticket.application.ScheduleTicketSlaAlertService;
import java.time.Instant;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.bean.override.mockito.MockitoBean;

@SpringBootTest(properties = {
        "supportflow.model.mock.enabled=true",
        "spring.datasource.url=jdbc:h2:mem:sla-transaction;MODE=MySQL;DB_CLOSE_DELAY=-1;DATABASE_TO_LOWER=TRUE"
})
class ScheduleTicketSlaAlertTransactionTest {
    @Autowired
    private ScheduleTicketSlaAlertService service;

    @Autowired
    private JdbcTemplate jdbc;

    @MockitoBean
    private OutboxService outbox;

    @Test
    void rollsBackTheAlertMarkerWhenOutboxRecordingFails() {
        SlaDeadline deadline = new SlaDeadline(7L, 9L, "FIRST_RESPONSE",
                Instant.parse("2026-08-09T00:00:00Z"));
        doThrow(new IllegalStateException("outbox unavailable")).when(outbox)
                .record(eq(7L), eq("ticket.sla.first_response"), eq("ticket"), eq("9"), anyString());

        TenantContext.set(new AuthenticatedPrincipal(0L, 7L, 0L, "SYSTEM"));
        try {
            assertThatThrownBy(() -> service.schedule(deadline))
                    .isInstanceOf(IllegalStateException.class)
                    .hasMessage("outbox unavailable");
        } finally {
            TenantContext.clear();
        }

        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM ticket_sla_alerts", Integer.class)).isZero();
    }
}
