package com.lqq.supportflow.knowledge.application;

import com.lqq.supportflow.knowledge.domain.KnowledgeBase;
import com.lqq.supportflow.knowledge.domain.KnowledgeBasePort;
import java.util.List;
import org.springframework.stereotype.Service;

@Service
public class ListKnowledgeBasesService {
    private final KnowledgeBasePort knowledgeBases;

    public ListKnowledgeBasesService(KnowledgeBasePort knowledgeBases) {
        this.knowledgeBases = knowledgeBases;
    }

    public List<KnowledgeBase> list(Long tenantId) {
        return knowledgeBases.list(tenantId);
    }
}
