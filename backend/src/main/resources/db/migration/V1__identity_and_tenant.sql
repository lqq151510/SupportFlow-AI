CREATE TABLE tenants (
    id BIGINT NOT NULL PRIMARY KEY,
    code VARCHAR(64) NOT NULL UNIQUE,
    name VARCHAR(128) NOT NULL,
    status VARCHAR(32) NOT NULL,
    created_at TIMESTAMP(3) NOT NULL,
    updated_at TIMESTAMP(3) NOT NULL,
    CONSTRAINT ck_tenants_status CHECK (status IN ('ACTIVE', 'DISABLED'))
);

CREATE TABLE users (
    id BIGINT NOT NULL PRIMARY KEY,
    email VARCHAR(254) NOT NULL UNIQUE,
    password_hash VARCHAR(100) NOT NULL,
    display_name VARCHAR(128) NOT NULL,
    status VARCHAR(32) NOT NULL,
    created_at TIMESTAMP(3) NOT NULL,
    updated_at TIMESTAMP(3) NOT NULL,
    CONSTRAINT ck_users_status CHECK (status IN ('ACTIVE', 'DISABLED'))
);

CREATE TABLE tenant_memberships (
    id BIGINT NOT NULL PRIMARY KEY,
    tenant_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    role VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL,
    created_at TIMESTAMP(3) NOT NULL,
    updated_at TIMESTAMP(3) NOT NULL,
    CONSTRAINT uk_tenant_memberships_tenant_user UNIQUE (tenant_id, user_id),
    CONSTRAINT fk_membership_tenant FOREIGN KEY (tenant_id) REFERENCES tenants (id),
    CONSTRAINT fk_membership_user FOREIGN KEY (user_id) REFERENCES users (id),
    CONSTRAINT ck_memberships_role CHECK (role IN ('TENANT_ADMIN', 'SUPERVISOR', 'AGENT', 'CUSTOMER')),
    CONSTRAINT ck_memberships_status CHECK (status IN ('ACTIVE', 'DISABLED'))
);

CREATE INDEX idx_memberships_tenant_role_status ON tenant_memberships (tenant_id, role, status);
