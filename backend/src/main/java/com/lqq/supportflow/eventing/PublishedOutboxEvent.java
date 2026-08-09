package com.lqq.supportflow.eventing;

public record PublishedOutboxEvent(Long id, Long tenantId, String eventType, String payload) { }
