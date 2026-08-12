ALTER TABLE approval_requests ADD COLUMN order_no VARCHAR(64);
ALTER TABLE approval_requests ADD COLUMN amount DECIMAL(12, 2);
ALTER TABLE approval_requests ADD COLUMN currency VARCHAR(3);
ALTER TABLE approval_requests ADD COLUMN eligibility_evidence VARCHAR(1000);

ALTER TABLE approval_decisions ADD COLUMN approval_version BIGINT NOT NULL DEFAULT 0;

ALTER TABLE action_executions ADD COLUMN execution_version BIGINT NOT NULL DEFAULT 1;
ALTER TABLE action_executions ADD COLUMN business_idempotency_key VARCHAR(128);
ALTER TABLE action_executions ADD CONSTRAINT uk_action_execution_business_key
    UNIQUE (tenant_id, business_idempotency_key);
