package com.lqq.supportflow.knowledge.domain;
public interface KnowledgeDocumentPort { boolean exists(Long tenantId,Long knowledgeBaseId,String contentHash); KnowledgeDocument save(Long tenantId,Long knowledgeBaseId,String fileName,String contentHash); KnowledgeDocument transitionStatus(Long tenantId,Long documentId,IngestionStatus from,IngestionStatus to); }
