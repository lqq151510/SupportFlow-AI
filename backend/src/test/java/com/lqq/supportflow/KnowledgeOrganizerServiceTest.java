package com.lqq.supportflow;

import static org.junit.jupiter.api.Assertions.*;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.lqq.supportflow.knowledge.application.KnowledgeOrganizerService;
import com.lqq.supportflow.knowledge.domain.*;
import com.lqq.supportflow.model.ModelChatService;
import com.lqq.supportflow.model.ModelUsageService;
import java.util.*;
import org.junit.jupiter.api.Test;

class KnowledgeOrganizerServiceTest {

    static class InMemoryDocPort implements KnowledgeDocumentPort {
        @Override public boolean exists(Long tenantId, Long knowledgeBaseId, String contentHash) { return false; }
        @Override public KnowledgeDocument save(Long tenantId, Long knowledgeBaseId, String fileName, String contentHash) { return null; }
        @Override public KnowledgeDocument transitionStatus(Long tenantId, Long documentId, IngestionStatus from, IngestionStatus to) { return null; }
        @Override public Optional<KnowledgeDocument> findById(Long tenantId, Long knowledgeBaseId, Long documentId) {
            return Optional.of(new KnowledgeDocument(documentId, "退款与售后规则.md", "hash123", IngestionStatus.INDEXED));
        }
        @Override public List<KnowledgeDocument> findByKnowledgeBase(Long tenantId, Long knowledgeBaseId) { return List.of(); }
        @Override public void attachObject(Long tenantId, Long documentId, String objectKey, String contentType) { }
        @Override public KnowledgeDocument markFailed(Long tenantId, Long documentId, String errorCode) { return null; }
    }

    static class InMemoryChunkPort implements KnowledgeChunkPort {
        @Override public List<KnowledgeChunk> saveAll(Long tenantId, Long knowledgeBaseId, Long documentId, List<String> contents) { return List.of(); }
        @Override public long count(Long tenantId, Long knowledgeBaseId, Long documentId) { return 1; }
        @Override public List<KnowledgeChunk> findByDocument(Long tenantId, Long knowledgeBaseId, Long documentId) {
            return List.of(new KnowledgeChunk(1L, documentId, 1, "支持 7 天无理由退货，商品需保持原包装完好。"));
        }
    }

    @Test
    void organizesDocumentWithConfiguredModel() {
        ModelChatService chatService = new ModelChatService(request -> reactor.core.publisher.Flux.empty(), new ObjectMapper());

        KnowledgeOrganizerService service = new KnowledgeOrganizerService(
                new InMemoryDocPort(),
                new InMemoryChunkPort(),
                chatService,
                null
        );

        KnowledgeOrganizerService.OrganizedKnowledgeResult result = service.organize(1L, 1L, 100L);
        assertNotNull(result);
        assertEquals(100L, result.documentId());
        assertEquals("退款与售后规则.md", result.fileName());
        assertFalse(result.summary().isBlank());
        assertFalse(result.tags().isEmpty());
    }
}
