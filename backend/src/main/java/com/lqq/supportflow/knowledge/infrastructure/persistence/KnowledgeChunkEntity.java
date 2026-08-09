package com.lqq.supportflow.knowledge.infrastructure.persistence;
import com.baomidou.mybatisplus.annotation.*; import java.time.Instant;
@TableName("knowledge_chunks") public class KnowledgeChunkEntity { @TableId(type=IdType.ASSIGN_ID) public Long id; public Long tenantId; public Long knowledgeBaseId; public Long documentId; public Integer chunkNo; public String content; public Instant createdAt; }
