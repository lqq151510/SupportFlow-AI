package com.lqq.supportflow.knowledge;

public record RetrievedCitation(Long knowledgeBaseId, Long documentId, Long chunkId, String content, double score, int rank) { }
