package com.lqq.supportflow.knowledge.domain;
import java.util.Optional;
public interface KnowledgeDocumentPort { boolean exists(Long tenantId,Long knowledgeBaseId,String contentHash); KnowledgeDocument save(Long tenantId,Long knowledgeBaseId,String fileName,String contentHash); KnowledgeDocument transitionStatus(Long tenantId,Long documentId,IngestionStatus from,IngestionStatus to); Optional<KnowledgeDocument> findById(Long tenantId,Long knowledgeBaseId,Long documentId); void attachObject(Long tenantId,Long documentId,String objectKey,String contentType); }
