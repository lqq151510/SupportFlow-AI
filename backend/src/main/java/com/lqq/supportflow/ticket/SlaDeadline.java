package com.lqq.supportflow.ticket;

import java.time.Instant;

public record SlaDeadline(Long tenantId, Long ticketId, String type, Instant dueAt) { }
