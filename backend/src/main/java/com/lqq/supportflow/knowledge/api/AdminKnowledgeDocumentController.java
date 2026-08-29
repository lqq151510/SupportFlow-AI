package com.lqq.supportflow.knowledge.api;

import com.lqq.supportflow.knowledge.application.*;
import com.lqq.supportflow.knowledge.domain.*;
import com.lqq.supportflow.shared.AuthenticatedPrincipal;
import jakarta.validation.Valid;
import java.util.List;
import java.util.Map;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

@RestController
@RequestMapping("/api/v1/admin/knowledge-bases/{knowledgeBaseId}/documents")
public class AdminKnowledgeDocumentController {

    private final RegisterKnowledgeDocumentService service;
    private final GetDocumentIngestionProgressService progress;
    private final UploadKnowledgeDocumentService uploads;
    private final IndexKnowledgeDocumentService indexing;
    private final RetryKnowledgeDocumentService retry;
    private final RebuildKnowledgeIndexService rebuild;
    private final ListKnowledgeDocumentsService list;
    private final KnowledgeOrganizerService organizer;

    @Autowired
    public AdminKnowledgeDocumentController(
            RegisterKnowledgeDocumentService service,
            GetDocumentIngestionProgressService progress,
            UploadKnowledgeDocumentService uploads,
            IndexKnowledgeDocumentService indexing,
            RetryKnowledgeDocumentService retry,
            RebuildKnowledgeIndexService rebuild,
            ListKnowledgeDocumentsService list,
            @Autowired(required = false) KnowledgeOrganizerService organizer) {
        this.service = service;
        this.progress = progress;
        this.uploads = uploads;
        this.indexing = indexing;
        this.retry = retry;
        this.rebuild = rebuild;
        this.list = list;
        this.organizer = organizer;
    }

    @GetMapping
    public List<KnowledgeDocument> list(@AuthenticationPrincipal AuthenticatedPrincipal p, @PathVariable Long knowledgeBaseId) {
        return list.list(p.tenantId(), knowledgeBaseId);
    }

    @PostMapping
    public ResponseEntity<KnowledgeDocument> register(
            @AuthenticationPrincipal AuthenticatedPrincipal p,
            @PathVariable Long knowledgeBaseId,
            @Valid @RequestBody RegisterKnowledgeDocumentRequest r) {
        return ResponseEntity.status(HttpStatus.CREATED).body(service.register(p.tenantId(), knowledgeBaseId, r.fileName(), r.content()));
    }

    @PostMapping(value = "/upload", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<KnowledgeDocument> upload(
            @AuthenticationPrincipal AuthenticatedPrincipal p,
            @PathVariable Long knowledgeBaseId,
            @RequestPart("file") MultipartFile file) {
        return ResponseEntity.status(HttpStatus.CREATED).body(uploads.upload(p.tenantId(), knowledgeBaseId, file));
    }

    @PostMapping("/{documentId}/index")
    public KnowledgeDocument index(@AuthenticationPrincipal AuthenticatedPrincipal p, @PathVariable Long knowledgeBaseId, @PathVariable Long documentId) {
        return indexing.index(p.tenantId(), knowledgeBaseId, documentId);
    }

    @PostMapping("/{documentId}/retry")
    public KnowledgeDocument retry(@AuthenticationPrincipal AuthenticatedPrincipal p, @PathVariable Long knowledgeBaseId, @PathVariable Long documentId) {
        return retry.retry(p.tenantId(), knowledgeBaseId, documentId);
    }

    @PostMapping("/{documentId}/organize")
    public KnowledgeOrganizerService.OrganizedKnowledgeResult organize(
            @AuthenticationPrincipal AuthenticatedPrincipal p,
            @PathVariable Long knowledgeBaseId,
            @PathVariable Long documentId) {
        if (organizer == null) {
            throw new IllegalStateException("knowledge organizer service not available");
        }
        return organizer.organize(p.tenantId(), knowledgeBaseId, documentId);
    }

    @PostMapping("/rebuild")
    public Map<String, Integer> rebuild(@AuthenticationPrincipal AuthenticatedPrincipal p, @PathVariable Long knowledgeBaseId) {
        return Map.of("reindexedChunks", rebuild.rebuild(p.tenantId(), knowledgeBaseId));
    }

    @GetMapping("/{documentId}")
    public DocumentIngestionProgress getProgress(@AuthenticationPrincipal AuthenticatedPrincipal p, @PathVariable Long knowledgeBaseId, @PathVariable Long documentId) {
        return progress.get(p.tenantId(), knowledgeBaseId, documentId);
    }
}
