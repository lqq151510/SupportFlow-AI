package com.lqq.supportflow.knowledge.domain;
public interface KnowledgeBasePort { KnowledgeBase create(Long tenantId,String name,String description); java.util.List<KnowledgeBase> list(Long tenantId); boolean belongsTo(Long tenantId,Long knowledgeBaseId); }
