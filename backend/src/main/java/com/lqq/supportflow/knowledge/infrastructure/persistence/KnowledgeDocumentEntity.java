package com.lqq.supportflow.knowledge.infrastructure.persistence;
import com.baomidou.mybatisplus.annotation.*; import java.time.Instant;
@TableName("knowledge_documents") public class KnowledgeDocumentEntity { @TableId(type=IdType.ASSIGN_ID) public Long id; public Long tenantId; public Long knowledgeBaseId; public String fileName; public String contentHash; public String objectKey; public String contentType; public String status; public String errorCode; public Integer retryCount; public Instant createdAt; public Instant updatedAt; }
