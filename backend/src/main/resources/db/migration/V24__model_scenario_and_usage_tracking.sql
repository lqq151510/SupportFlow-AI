ALTER TABLE model_configs ADD is_knowledge_default BOOLEAN NOT NULL DEFAULT FALSE;
CREATE INDEX idx_model_configs_tenant_knowledge ON model_configs (tenant_id, is_knowledge_default);

CREATE TABLE model_usage_records (
    id BIGINT NOT NULL PRIMARY KEY,
    tenant_id BIGINT NOT NULL,
    scenario VARCHAR(64) NOT NULL,
    model_name VARCHAR(128) NOT NULL,
    protocol VARCHAR(32) NOT NULL,
    input_tokens INT NOT NULL DEFAULT 0,
    output_tokens INT NOT NULL DEFAULT 0,
    total_tokens INT NOT NULL DEFAULT 0,
    latency_ms BIGINT NOT NULL DEFAULT 0,
    estimated_cost_cny DECIMAL(12, 6) NOT NULL DEFAULT 0,
    estimated_cost_usd DECIMAL(12, 6) NOT NULL DEFAULT 0,
    created_at TIMESTAMP(3) NOT NULL,
    CONSTRAINT fk_model_usage_tenant FOREIGN KEY (tenant_id) REFERENCES tenants (id)
);

CREATE INDEX idx_model_usage_tenant_time ON model_usage_records (tenant_id, created_at);
CREATE INDEX idx_model_usage_tenant_scenario ON model_usage_records (tenant_id, scenario);
