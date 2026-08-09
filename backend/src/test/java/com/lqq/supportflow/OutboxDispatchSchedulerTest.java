package com.lqq.supportflow;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import com.lqq.supportflow.eventing.application.DispatchOutboxService;
import com.lqq.supportflow.eventing.application.OutboxDispatchScheduler;
import com.lqq.supportflow.shared.ActiveTenantProvider;
import com.lqq.supportflow.shared.TenantContext;
import java.util.ArrayList;
import java.util.List;
import org.junit.jupiter.api.Test;

class OutboxDispatchSchedulerTest {

    @Test
    void dispatchesEachTenantWithAnIsolatedContext() {
        DispatchOutboxService dispatch = mock(DispatchOutboxService.class);
        ActiveTenantProvider tenants = mock(ActiveTenantProvider.class);
        List<Long> dispatchedTenantIds = new ArrayList<>();
        when(tenants.findActiveTenantIds()).thenReturn(List.of(7L, 9L));
        doAnswer(ignored -> {
            dispatchedTenantIds.add(TenantContext.current().orElseThrow().tenantId());
            return 0;
        }).when(dispatch).dispatch(anyInt());

        new OutboxDispatchScheduler(dispatch, tenants).dispatchPendingEvents();

        assertThat(dispatchedTenantIds).containsExactly(7L, 9L);
        assertThat(TenantContext.current()).isEmpty();
    }
}
