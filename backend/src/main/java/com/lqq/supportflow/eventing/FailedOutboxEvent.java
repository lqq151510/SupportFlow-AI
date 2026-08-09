package com.lqq.supportflow.eventing;

import java.time.Instant;

public record FailedOutboxEvent(Long id, String eventType, String aggregateType, String aggregateId, int attemptCount, String lastError, Instant failedAt) { }
