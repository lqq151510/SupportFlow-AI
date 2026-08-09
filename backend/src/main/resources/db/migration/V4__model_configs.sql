CREATE TABLE model_configs (
    id BIGINT NOT NULL PRIMARY KEY,
    tenant_id BIGINT NOT NULL,
    name VARCHAR(128) NOT NULL,
    protocol VARCHAR(32) NOT NULL,
    base_url VARCHAR(512) NOT NULL,
    model_name VARCHAR(128) NOT NULL,
    encrypted_api_key TEXT NOT NULL,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP(3) NOT NULL,
    updated_at TIMESTAMP(3) NOT NULL,
    CONSTRAINT uk_model_configs_tenant_name UNIQUE (tenant_id, name),
    CONSTRAINT fk_model_configs_tenant FOREIGN KEY (tenant_id) REFERENCES tenants (id)
);
CREATE INDEX idx_model_configs_tenant_default ON model_configs (tenant_id, is_default);
