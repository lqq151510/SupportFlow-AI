CREATE TABLE tickets (
 id BIGINT NOT NULL PRIMARY KEY, tenant_id BIGINT NOT NULL, customer_id BIGINT NOT NULL, conversation_id BIGINT NOT NULL, title VARCHAR(255) NOT NULL, status VARCHAR(32) NOT NULL, priority VARCHAR(16) NOT NULL, assigned_membership_id BIGINT, first_response_due_at TIMESTAMP(3) NOT NULL, resolution_due_at TIMESTAMP(3) NOT NULL, version BIGINT NOT NULL, created_at TIMESTAMP(3) NOT NULL, updated_at TIMESTAMP(3) NOT NULL,
 CONSTRAINT fk_tickets_conversation FOREIGN KEY (conversation_id) REFERENCES conversations(id));
CREATE INDEX idx_tickets_tenant_status ON tickets(tenant_id,status,priority,created_at);
