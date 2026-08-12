package com.lqq.supportflow;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import com.lqq.supportflow.ticket.SlaDeadline;
import com.lqq.supportflow.ticket.infrastructure.persistence.MyBatisSlaMonitorAdapter;
import com.lqq.supportflow.ticket.infrastructure.persistence.TicketEntity;
import com.lqq.supportflow.ticket.infrastructure.persistence.TicketMapper;
import com.lqq.supportflow.ticket.infrastructure.persistence.TicketSlaAlertEntity;
import com.lqq.supportflow.ticket.infrastructure.persistence.TicketSlaAlertMapper;
import java.time.Instant;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.springframework.dao.DuplicateKeyException;

class MyBatisSlaMonitorAdapterTest {

    @Test
    void returnsBothDeadlineTypesAndKeepsDuplicateAlertsIdempotent() {
        TicketMapper tickets = mock(TicketMapper.class);
        TicketSlaAlertMapper alerts = mock(TicketSlaAlertMapper.class);
        Instant now = Instant.parse("2026-08-12T00:00:00Z");
        TicketEntity firstResponseDue = ticket(10L, now.minusSeconds(30), now.plusSeconds(300));
        TicketEntity resolutionDue = ticket(11L, now.plusSeconds(300), now.minusSeconds(30));
        when(tickets.selectList(any())).thenReturn(List.of(firstResponseDue), List.of(resolutionDue));
        when(alerts.insert(any(TicketSlaAlertEntity.class))).thenReturn(1).thenThrow(new DuplicateKeyException("duplicate"));

        MyBatisSlaMonitorAdapter adapter = new MyBatisSlaMonitorAdapter(tickets, alerts);

        assertThat(adapter.dueAt(now))
                .containsExactly(
                        new SlaDeadline(7L, 10L, "FIRST_RESPONSE", firstResponseDue.firstResponseDueAt),
                        new SlaDeadline(7L, 11L, "RESOLUTION", resolutionDue.resolutionDueAt));
        SlaDeadline deadline = new SlaDeadline(7L, 10L, "FIRST_RESPONSE", now);
        assertThat(adapter.markAlerted(deadline)).isTrue();
        assertThat(adapter.markAlerted(deadline)).isFalse();
    }

    private TicketEntity ticket(Long id, Instant firstResponseDueAt, Instant resolutionDueAt) {
        TicketEntity ticket = new TicketEntity();
        ticket.id = id;
        ticket.tenantId = 7L;
        ticket.firstResponseDueAt = firstResponseDueAt;
        ticket.resolutionDueAt = resolutionDueAt;
        return ticket;
    }
}
