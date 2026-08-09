package com.lqq.supportflow;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.lqq.supportflow.eventing.application.DispatchOutboxService;
import com.lqq.supportflow.eventing.domain.OutboxDeliveryGateway;
import com.lqq.supportflow.eventing.domain.OutboxEvent;
import com.lqq.supportflow.eventing.domain.OutboxPort;
import java.time.Instant;
import java.util.List;
import org.junit.jupiter.api.Test;

class DispatchOutboxServiceTest {
    @Test
    void recordsFailureAndContinuesDispatchingOtherEvents() {
        OutboxPort outbox = mock(OutboxPort.class);
        OutboxDeliveryGateway delivery = mock(OutboxDeliveryGateway.class);
        OutboxEvent failed = event(1L);
        OutboxEvent delivered = event(2L);
        when(outbox.pending(10)).thenReturn(List.of(failed, delivered));
        doThrow(new IllegalStateException("broker unavailable")).when(delivery).publish(failed);

        assertThat(new DispatchOutboxService(outbox, delivery).dispatch(10)).isEqualTo(1);

        verify(outbox).recordFailure(1L, "broker unavailable");
        verify(outbox).markPublished(2L);
    }

    private OutboxEvent event(Long id) {
        return new OutboxEvent(id, 7L, "approval.approved", "approval", "9", "{}", 0, Instant.now());
    }
}
