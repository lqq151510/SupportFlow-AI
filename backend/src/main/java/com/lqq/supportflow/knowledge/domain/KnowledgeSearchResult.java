package com.lqq.supportflow.knowledge.domain;
import java.util.List;
public record KnowledgeSearchResult(Long searchId,List<KnowledgeCitation> citations) { }
