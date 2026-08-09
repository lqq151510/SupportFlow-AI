package com.lqq.supportflow.knowledge.domain;
import java.util.List;
public interface KnowledgeChunkPort { List<KnowledgeChunk> saveAll(Long tenantId,Long knowledgeBaseId,Long documentId,List<String> contents); long count(Long tenantId,Long knowledgeBaseId,Long documentId); }
