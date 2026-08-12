ALTER TABLE knowledge_bases ADD COLUMN version BIGINT NOT NULL DEFAULT 1;
ALTER TABLE knowledge_searches ADD COLUMN knowledge_base_version BIGINT NOT NULL DEFAULT 1;
