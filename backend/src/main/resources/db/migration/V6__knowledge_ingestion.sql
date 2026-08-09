CREATE TABLE knowledge_bases (
 id BIGINT NOT NULL PRIMARY KEY, tenant_id BIGINT NOT NULL, name VARCHAR(128) NOT NULL, description VARCHAR(512), status VARCHAR(32) NOT NULL, created_at TIMESTAMP(3) NOT NULL, updated_at TIMESTAMP(3) NOT NULL,
 CONSTRAINT uk_knowledge_bases_tenant_name UNIQUE (tenant_id,name), CONSTRAINT fk_knowledge_bases_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id));
CREATE TABLE knowledge_documents (
 id BIGINT NOT NULL PRIMARY KEY, tenant_id BIGINT NOT NULL, knowledge_base_id BIGINT NOT NULL, file_name VARCHAR(255) NOT NULL, content_hash CHAR(64) NOT NULL, status VARCHAR(32) NOT NULL, error_code VARCHAR(64), retry_count INT NOT NULL DEFAULT 0, created_at TIMESTAMP(3) NOT NULL, updated_at TIMESTAMP(3) NOT NULL,
 CONSTRAINT uk_knowledge_documents_hash UNIQUE (tenant_id,knowledge_base_id,content_hash), CONSTRAINT fk_knowledge_documents_base FOREIGN KEY (knowledge_base_id) REFERENCES knowledge_bases(id));
CREATE INDEX idx_knowledge_documents_tenant_status ON knowledge_documents(tenant_id,status,created_at);
