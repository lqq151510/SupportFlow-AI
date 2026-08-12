CREATE TABLE knowledge_chunks (
 id BIGINT NOT NULL PRIMARY KEY, tenant_id BIGINT NOT NULL, knowledge_base_id BIGINT NOT NULL, document_id BIGINT NOT NULL, chunk_no INT NOT NULL, content LONGTEXT NOT NULL, created_at TIMESTAMP(3) NOT NULL,
 CONSTRAINT uk_knowledge_chunks_document_no UNIQUE (document_id,chunk_no),
 CONSTRAINT fk_knowledge_chunks_document FOREIGN KEY (document_id) REFERENCES knowledge_documents(id));
CREATE INDEX idx_knowledge_chunks_tenant_base ON knowledge_chunks(tenant_id,knowledge_base_id,document_id);
