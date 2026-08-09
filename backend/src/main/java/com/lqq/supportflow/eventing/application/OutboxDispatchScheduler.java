package com.lqq.supportflow.eventing.application;

import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Component
public class OutboxDispatchScheduler {
    private final DispatchOutboxService dispatch;

    public OutboxDispatchScheduler(DispatchOutboxService dispatch) {
        this.dispatch = dispatch;
    }

    @Scheduled(initialDelayString = "${supportflow.eventing.dispatch.initial-delay:PT30S}", fixedDelayString = "${supportflow.eventing.dispatch.fixed-delay:PT30S}")
    public void dispatchPendingEvents() {
        dispatch.dispatch(100);
    }
}
