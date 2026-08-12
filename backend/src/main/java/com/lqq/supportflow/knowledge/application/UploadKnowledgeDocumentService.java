package com.lqq.supportflow.knowledge.application;

import com.lqq.supportflow.knowledge.domain.ContentHasher;
import com.lqq.supportflow.knowledge.domain.DocumentTextExtractor;
import com.lqq.supportflow.knowledge.domain.KnowledgeDocument;
import com.lqq.supportflow.knowledge.domain.KnowledgeDocumentPort;
import com.lqq.supportflow.knowledge.domain.KnowledgeObjectStorage;
import com.lqq.supportflow.knowledge.domain.StoredKnowledgeObject;
import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.io.InputStream;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

@Service
public class UploadKnowledgeDocumentService {
    private static final long MAX_FILE_SIZE = 20L * 1024 * 1024;

    private final KnowledgeObjectStorage storage;
    private final DocumentTextExtractor extractor;
    private final RegisterKnowledgeDocumentService registration;
    private final KnowledgeDocumentPort documents;
    private final KnowledgeIndexingFailureHandler indexing;
    private final KnowledgeFilePolicy filePolicy;

    public UploadKnowledgeDocumentService(KnowledgeObjectStorage storage, DocumentTextExtractor extractor,
                                          RegisterKnowledgeDocumentService registration,
                                          KnowledgeDocumentPort documents,
                                          KnowledgeIndexingFailureHandler indexing,
                                          KnowledgeFilePolicy filePolicy) {
        this.storage = storage;
        this.extractor = extractor;
        this.registration = registration;
        this.documents = documents;
        this.indexing = indexing;
        this.filePolicy = filePolicy;
    }

    public KnowledgeDocument upload(Long tenantId, Long knowledgeBaseId, MultipartFile file) {
        if (file.isEmpty()) throw new IllegalArgumentException("document file is empty");
        if (file.getSize() > MAX_FILE_SIZE) throw new IllegalArgumentException("document file exceeds 20 MB");
        try {
            byte[] bytes = file.getBytes();
            String type = filePolicy.validate(file.getOriginalFilename(), file.getContentType(), bytes);
            String hash = ContentHasher.sha256(bytes);
            StoredKnowledgeObject stored = storage.put(tenantId, knowledgeBaseId, hash,
                    file.getOriginalFilename(), type, new ByteArrayInputStream(bytes), bytes.length);
            String text;
            try (InputStream input = storage.open(stored.objectKey())) {
                text = extractor.extract(input, type);
            }
            KnowledgeDocument document = registration.registerExtracted(
                    tenantId, knowledgeBaseId, file.getOriginalFilename(), hash, text);
            documents.attachObject(tenantId, document.id(), stored.objectKey(), type);
            return indexing.index(tenantId, knowledgeBaseId, document.id());
        } catch (IOException exception) {
            throw new IllegalArgumentException("cannot read uploaded document", exception);
        }
    }
}
