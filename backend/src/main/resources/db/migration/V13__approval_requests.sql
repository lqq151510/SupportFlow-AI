CREATE TABLE approval_requests (
 id BIGINT NOT NULL PRIMARY KEY, tenant_id BIGINT NOT NULL, customer_id BIGINT, action_type VARCHAR(64) NOT NULL, action_summary VARCHAR(1000) NOT NULL, status VARCHAR(32) NOT NULL, requested_by_membership_id BIGINT, decided_by_membership_id BIGINT, expires_at TIMESTAMP(3) NOT NULL, version BIGINT NOT NULL, created_at TIMESTAMP(3) NOT NULL, updated_at TIMESTAMP(3) NOT NULL);
CREATE TABLE approval_decisions (
 id BIGINT NOT NULL PRIMARY KEY, tenant_id BIGINT NOT NULL, approval_id BIGINT NOT NULL, idempotency_key VARCHAR(128) NOT NULL, decision VARCHAR(32) NOT NULL, created_at TIMESTAMP(3) NOT NULL,
 CONSTRAINT uk_approval_decision_idempotency UNIQUE (tenant_id,approval_id,idempotency_key), CONSTRAINT fk_approval_decisions_request FOREIGN KEY (approval_id) REFERENCES approval_requests(id));
CREATE INDEX idx_approval_requests_tenant_status ON approval_requests(tenant_id,status,expires_at);
