CREATE TABLE evaluation_cases (
 id BIGINT NOT NULL PRIMARY KEY,
 tenant_id BIGINT NOT NULL,
 knowledge_base_id BIGINT NOT NULL,
 question VARCHAR(2000) NOT NULL,
 expected_document_id BIGINT NOT NULL,
 category VARCHAR(80) NOT NULL,
 enabled BOOLEAN NOT NULL DEFAULT TRUE,
 created_at TIMESTAMP(3) NOT NULL,
 updated_at TIMESTAMP(3) NOT NULL,
 CONSTRAINT fk_evaluation_cases_base FOREIGN KEY (knowledge_base_id) REFERENCES knowledge_bases(id),
 CONSTRAINT fk_evaluation_cases_document FOREIGN KEY (expected_document_id) REFERENCES knowledge_documents(id)
);
CREATE INDEX idx_evaluation_cases_tenant_base_enabled ON evaluation_cases(tenant_id, knowledge_base_id, enabled, created_at);

CREATE TABLE evaluation_runs (
 id BIGINT NOT NULL PRIMARY KEY,
 tenant_id BIGINT NOT NULL,
 knowledge_base_id BIGINT NOT NULL,
 knowledge_base_version BIGINT NOT NULL,
 status VARCHAR(32) NOT NULL,
 total_cases INT NOT NULL,
 evaluated_cases INT NOT NULL DEFAULT 0,
 failed_cases INT NOT NULL DEFAULT 0,
 recall_at_1 DECIMAL(8,6),
 recall_at_3 DECIMAL(8,6),
 recall_at_6 DECIMAL(8,6),
 started_at TIMESTAMP(3) NOT NULL,
 completed_at TIMESTAMP(3),
 CONSTRAINT fk_evaluation_runs_base FOREIGN KEY (knowledge_base_id) REFERENCES knowledge_bases(id)
);
CREATE INDEX idx_evaluation_runs_tenant_base_created ON evaluation_runs(tenant_id, knowledge_base_id, started_at DESC);

CREATE TABLE evaluation_results (
 id BIGINT NOT NULL PRIMARY KEY,
 tenant_id BIGINT NOT NULL,
 run_id BIGINT NOT NULL,
 case_id BIGINT NOT NULL,
 status VARCHAR(32) NOT NULL,
 expected_document_id BIGINT NOT NULL,
 hit_rank INT,
 top_score DECIMAL(12,8),
 latency_ms BIGINT,
 failure_code VARCHAR(80),
 created_at TIMESTAMP(3) NOT NULL,
 CONSTRAINT uk_evaluation_results_run_case UNIQUE (run_id, case_id),
 CONSTRAINT fk_evaluation_results_run FOREIGN KEY (run_id) REFERENCES evaluation_runs(id),
 CONSTRAINT fk_evaluation_results_case FOREIGN KEY (case_id) REFERENCES evaluation_cases(id)
);
CREATE INDEX idx_evaluation_results_tenant_run ON evaluation_results(tenant_id, run_id, created_at);
