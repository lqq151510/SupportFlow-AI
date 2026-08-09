package com.lqq.supportflow.knowledge.domain;
import java.util.List;
public interface KnowledgeSearchIndex { void index(Long tenantId,Long knowledgeBaseId,Long documentId,List<IndexedKnowledgeChunk> chunks); }
