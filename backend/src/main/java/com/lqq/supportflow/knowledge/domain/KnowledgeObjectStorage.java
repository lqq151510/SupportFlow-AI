package com.lqq.supportflow.knowledge.domain;
import java.io.InputStream;
public interface KnowledgeObjectStorage { StoredKnowledgeObject put(Long tenantId,Long knowledgeBaseId,String contentHash,String fileName,String contentType,InputStream content,long size); InputStream open(String objectKey); }
