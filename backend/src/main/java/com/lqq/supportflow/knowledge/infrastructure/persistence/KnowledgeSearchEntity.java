package com.lqq.supportflow.knowledge.infrastructure.persistence;
import com.baomidou.mybatisplus.annotation.*; import java.time.Instant;
@TableName("knowledge_searches") public class KnowledgeSearchEntity { @TableId(type=IdType.ASSIGN_ID) public Long id; public Long tenantId; public Long knowledgeBaseId; public String queryText; public Instant createdAt; }
