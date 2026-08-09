package com.lqq.supportflow.knowledge.infrastructure.persistence;
import com.baomidou.mybatisplus.annotation.*; import java.time.Instant;
@TableName("knowledge_bases") public class KnowledgeBaseEntity { @TableId(type=IdType.ASSIGN_ID) public Long id; public Long tenantId; public String name; public String description; public String status; public Instant createdAt; public Instant updatedAt; }
