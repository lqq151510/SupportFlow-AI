package com.lqq.supportflow.knowledge.domain;
public interface KnowledgeBasePort { KnowledgeBase create(Long tenantId,String name,String description); boolean belongsTo(Long tenantId,Long knowledgeBaseId); }
