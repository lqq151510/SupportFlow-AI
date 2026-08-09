package com.lqq.supportflow.knowledge.domain;
import java.util.List;
public interface KnowledgeSearchIndex { void index(Long tenantId,Long knowledgeBaseId,Long documentId,List<IndexedKnowledgeChunk> chunks); List<RankedKnowledgeChunk> keywordSearch(Long tenantId,Long knowledgeBaseId,String query,int limit); List<RankedKnowledgeChunk> vectorSearch(Long tenantId,Long knowledgeBaseId,float[] query,int limit); }
