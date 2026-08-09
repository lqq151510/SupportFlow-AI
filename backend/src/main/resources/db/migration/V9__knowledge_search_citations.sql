CREATE TABLE knowledge_searches (
 id BIGINT NOT NULL PRIMARY KEY, tenant_id BIGINT NOT NULL, knowledge_base_id BIGINT NOT NULL, query_text VARCHAR(2000) NOT NULL, created_at TIMESTAMP(3) NOT NULL,
 CONSTRAINT fk_knowledge_searches_base FOREIGN KEY (knowledge_base_id) REFERENCES knowledge_bases(id));
CREATE TABLE knowledge_search_citations (
 id BIGINT NOT NULL PRIMARY KEY, tenant_id BIGINT NOT NULL, search_id BIGINT NOT NULL, document_id BIGINT NOT NULL, chunk_id BIGINT NOT NULL, score DECIMAL(12,8) NOT NULL, rank_no INT NOT NULL, created_at TIMESTAMP(3) NOT NULL,
 CONSTRAINT uk_knowledge_search_citation_rank UNIQUE (search_id,rank_no), CONSTRAINT fk_knowledge_search_citations_search FOREIGN KEY (search_id) REFERENCES knowledge_searches(id));
CREATE INDEX idx_knowledge_searches_tenant_base ON knowledge_searches(tenant_id,knowledge_base_id,created_at);
