package com.lqq.supportflow.knowledge.infrastructure.persistence;
import com.baomidou.mybatisplus.annotation.*; import java.math.BigDecimal; import java.time.Instant;
@TableName("knowledge_search_citations") public class KnowledgeSearchCitationEntity { @TableId(type=IdType.ASSIGN_ID) public Long id; public Long tenantId; public Long searchId; public Long documentId; public Long chunkId; public BigDecimal score; public Integer rankNo; public Instant createdAt; }
