CREATE TABLE refresh_tokens (
    id BIGINT NOT NULL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    tenant_id BIGINT NOT NULL,
    jti VARCHAR(64) NOT NULL UNIQUE,
    token_hash CHAR(64) NOT NULL,
    expires_at TIMESTAMP(3) NOT NULL,
    revoked_at TIMESTAMP(3) NULL,
    created_at TIMESTAMP(3) NOT NULL,
    CONSTRAINT fk_refresh_token_user FOREIGN KEY (user_id) REFERENCES users (id),
    CONSTRAINT fk_refresh_token_tenant FOREIGN KEY (tenant_id) REFERENCES tenants (id)
);
CREATE INDEX idx_refresh_tokens_user_expiry ON refresh_tokens (user_id, expires_at);
