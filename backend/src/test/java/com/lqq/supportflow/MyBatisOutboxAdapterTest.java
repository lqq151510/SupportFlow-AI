package com.lqq.supportflow;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.lqq.supportflow.eventing.FailedOutboxEvent;
import com.lqq.supportflow.eventing.domain.OutboxEvent;
import com.lqq.supportflow.eventing.infrastructure.persistence.MyBatisOutboxAdapter;
import com.lqq.supportflow.eventing.infrastructure.persistence.OutboxEntity;
import com.lqq.supportflow.eventing.infrastructure.persistence.OutboxMapper;
import java.time.Instant;
import java.util.List;
import org.junit.jupiter.api.Test;

class MyBatisOutboxAdapterTest {

    @Test
    void recordsAndMapsPendingAndFailedEvents() {
        OutboxMapper mapper = mock(OutboxMapper.class);
        OutboxEntity pending = event("PENDING", 2);
        OutboxEntity failed = event("FAILED", 8);
        failed.lastError = "broker unavailable";
        failed.failedAt = Instant.parse("2026-08-12T00:00:00Z");
        when(mapper.selectList(any())).thenReturn(List.of(pending), List.of(failed));
        MyBatisOutboxAdapter adapter = new MyBatisOutboxAdapter(mapper);

        adapter.record(7L, "ticket.created", "ticket", "10", "{}");
        assertThat(adapter.pending(20)).containsExactly(new OutboxEvent(10L, 7L, "ticket.created", "ticket", "10", "{}", 2, pending.createdAt));
        assertThat(adapter.failed(7L, 20)).containsExactly(new FailedOutboxEvent(10L, "ticket.created", "ticket", "10", 8, "broker unavailable", failed.failedAt));
        verify(mapper).insert(any(OutboxEntity.class));
    }

    @Test
    void retriesPendingEventsAndStopsAfterTheMaximumAttemptCount() {
        OutboxMapper mapper = mock(OutboxMapper.class);
        OutboxEntity retryable = event("PENDING", 0);
        when(mapper.selectById(10L)).thenReturn(retryable);
        MyBatisOutboxAdapter adapter = new MyBatisOutboxAdapter(mapper);

        adapter.recordFailure(10L, "timeout");
        verify(mapper).update(any(OutboxEntity.class), any());

        retryable.attemptCount = 7;
        adapter.recordFailure(10L, "timeout");
        verify(mapper, org.mockito.Mockito.times(2)).update(any(OutboxEntity.class), any());
    }

    @Test
    void ignoresMissingAndAlreadyCompletedEvents() {
        OutboxMapper mapper = mock(OutboxMapper.class);
        when(mapper.selectById(10L)).thenReturn(null, event("PUBLISHED", 1));
        MyBatisOutboxAdapter adapter = new MyBatisOutboxAdapter(mapper);

        adapter.recordFailure(10L, "timeout");
        adapter.recordFailure(10L, "timeout");
        org.mockito.Mockito.verify(mapper, org.mockito.Mockito.never()).update(any(OutboxEntity.class), any());
    }

    private OutboxEntity event(String status, int attempts) {
        OutboxEntity event = new OutboxEntity();
        event.id = 10L;
        event.tenantId = 7L;
        event.eventType = "ticket.created";
        event.aggregateType = "ticket";
        event.aggregateId = "10";
        event.payload = "{}";
        event.status = status;
        event.attemptCount = attempts;
        event.createdAt = Instant.parse("2026-08-12T00:00:00Z");
        return event;
    }
}
