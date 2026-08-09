package com.lqq.supportflow.knowledge.domain;
import java.util.List;
public interface KnowledgeSearchAuditPort { Long save(Long tenantId,Long knowledgeBaseId,String query,List<KnowledgeCitation> citations); }
