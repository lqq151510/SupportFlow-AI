package com.lqq.supportflow.knowledge.domain;
public record KnowledgeDocument(Long id,String fileName,String contentHash,IngestionStatus status) { }
