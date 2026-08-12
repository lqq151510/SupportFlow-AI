package com.lqq.supportflow.eventing.api;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.lqq.supportflow.eventing.FailedOutboxEvent;
import com.lqq.supportflow.eventing.OutboxService;
import com.lqq.supportflow.eventing.application.DispatchOutboxService;
import com.lqq.supportflow.shared.AuthenticatedPrincipal;
import java.time.Instant;
import java.util.List;
import org.junit.jupiter.api.Test;

class AdminOutboxControllerTest {

    @Test
    void dispatchesWithinTheAllowedRangeAndReturnsPublishedCount() {
        DispatchOutboxService dispatch = mock(DispatchOutboxService.class);
        when(dispatch.dispatch(100)).thenReturn(3);
        AdminOutboxController controller = new AdminOutboxController(dispatch, mock(OutboxService.class));

        assertThat(controller.dispatch(100)).containsEntry("published", 3);
        verify(dispatch).dispatch(100);
    }

    @Test
    void rejectsDispatchAndFailedEventLimitsOutsideTheAllowedRange() {
        AdminOutboxController controller = new AdminOutboxController(mock(DispatchOutboxService.class), mock(OutboxService.class));
        AuthenticatedPrincipal principal = new AuthenticatedPrincipal(1L, 7L, 2L, "ADMIN");

        for (int invalid : List.of(0, 1001)) {
            assertThatThrownBy(() -> controller.dispatch(invalid))
                    .isInstanceOf(IllegalArgumentException.class).hasMessage("dispatch limit must be between 1 and 1000");
            assertThatThrownBy(() -> controller.failed(principal, invalid))
                    .isInstanceOf(IllegalArgumentException.class).hasMessage("limit must be between 1 and 1000");
        }
    }

    @Test
    void readsFailedEventsOnlyForTheAuthenticatedTenant() {
        OutboxService outbox = mock(OutboxService.class);
        FailedOutboxEvent failed = new FailedOutboxEvent(10L, "ticket.created", "ticket", "10", 8, "timeout", Instant.parse("2026-08-12T00:00:00Z"));
        when(outbox.failed(7L, 25)).thenReturn(List.of(failed));
        AdminOutboxController controller = new AdminOutboxController(mock(DispatchOutboxService.class), outbox);

        assertThat(controller.failed(new AuthenticatedPrincipal(1L, 7L, 2L, "ADMIN"), 25)).containsExactly(failed);
        verify(outbox).failed(7L, 25);
    }
}
