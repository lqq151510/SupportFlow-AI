package com.lqq.supportflow.knowledge.domain;
public record KnowledgeDocument(@com.fasterxml.jackson.databind.annotation.JsonSerialize(using=com.fasterxml.jackson.databind.ser.std.ToStringSerializer.class) Long id,String fileName,String contentHash,IngestionStatus status) { }
