CREATE TABLE action_executions (
 id BIGINT NOT NULL PRIMARY KEY, tenant_id BIGINT NOT NULL, approval_id BIGINT NOT NULL, action_type VARCHAR(64) NOT NULL, status VARCHAR(32) NOT NULL, executed_at TIMESTAMP(3) NOT NULL,
 CONSTRAINT uk_action_executions_approval UNIQUE (approval_id));
CREATE INDEX idx_action_executions_tenant ON action_executions(tenant_id,action_type,executed_at);
