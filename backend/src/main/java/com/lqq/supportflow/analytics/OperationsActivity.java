package com.lqq.supportflow.analytics;

import java.time.Instant;

/** Metadata-only operational activity. It intentionally contains no customer conversation content. */
public record OperationsActivity(String type, String title, String detail, Instant occurredAt) { }
