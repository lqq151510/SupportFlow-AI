package com.lqq.supportflow.analytics;

/**
 * Tenant-scoped runtime retrieval observability. These values are derived from persisted search audits,
 * not from an offline benchmark or a model-quality claim.
 */
public record RagOperations(
        long searches,
        long searchesWithCitations,
        double citationCoverage,
        double noEvidenceRate,
        double averageTopScore) { }
