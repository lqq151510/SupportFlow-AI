package com.lqq.supportflow.analytics;

public record OperationsOverview(long completedGenerations, long handoffGenerations, double aiResolutionRate, long overdueTickets, long inputTokens, long outputTokens, long averageGenerationLatencyMs) { }
