package com.lqq.supportflow.analytics;

/** Current tenant knowledge ingestion facts; processing excludes indexed and failed documents. */
public record KnowledgeOperations(
        long documents,
        long indexedDocuments,
        long processingDocuments,
        long failedDocuments,
        long chunks) { }
