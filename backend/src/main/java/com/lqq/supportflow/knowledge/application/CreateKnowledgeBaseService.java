package com.lqq.supportflow.knowledge.application;
import com.lqq.supportflow.knowledge.domain.*; import org.springframework.stereotype.Service; import org.springframework.transaction.annotation.Transactional;
@Service public class CreateKnowledgeBaseService { private final KnowledgeBasePort bases; public CreateKnowledgeBaseService(KnowledgeBasePort bases){this.bases=bases;} @Transactional public KnowledgeBase create(Long tenantId,String name,String description){return bases.create(tenantId,name,description);}}
