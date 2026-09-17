package com.lqq.supportflow.analytics;

/** Tenant-scoped completed and handoff generations for one UTC calendar day. */
public record DailyOperations(String day, long completedGenerations, long handoffGenerations) { }
