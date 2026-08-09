package com.lqq.supportflow.knowledge.domain;
public record DocumentIngestionProgress(Long documentId,IngestionStatus status,long chunkCount) { }
