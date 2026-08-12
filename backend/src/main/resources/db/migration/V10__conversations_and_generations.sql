CREATE TABLE conversations (
 id BIGINT NOT NULL PRIMARY KEY, tenant_id BIGINT NOT NULL, customer_id BIGINT NOT NULL, status VARCHAR(32) NOT NULL, created_at TIMESTAMP(3) NOT NULL, updated_at TIMESTAMP(3) NOT NULL,
 CONSTRAINT fk_conversations_customer FOREIGN KEY (customer_id) REFERENCES users(id));
CREATE TABLE conversation_messages (
 id BIGINT NOT NULL PRIMARY KEY, tenant_id BIGINT NOT NULL, conversation_id BIGINT NOT NULL, sender_type VARCHAR(16) NOT NULL, content LONGTEXT NOT NULL, idempotency_key VARCHAR(128), generation_id BIGINT, created_at TIMESTAMP(3) NOT NULL,
 CONSTRAINT uk_conversation_message_idempotency UNIQUE (tenant_id,conversation_id,idempotency_key), CONSTRAINT fk_conversation_messages_conversation FOREIGN KEY (conversation_id) REFERENCES conversations(id));
CREATE TABLE generations (
 id BIGINT NOT NULL PRIMARY KEY, tenant_id BIGINT NOT NULL, conversation_id BIGINT NOT NULL, user_message_id BIGINT NOT NULL, status VARCHAR(32) NOT NULL, error_code VARCHAR(64), created_at TIMESTAMP(3) NOT NULL, updated_at TIMESTAMP(3) NOT NULL,
 CONSTRAINT fk_generations_conversation FOREIGN KEY (conversation_id) REFERENCES conversations(id), CONSTRAINT fk_generations_message FOREIGN KEY (user_message_id) REFERENCES conversation_messages(id));
CREATE INDEX idx_conversations_tenant_customer ON conversations(tenant_id,customer_id,updated_at);
CREATE INDEX idx_generations_tenant_status ON generations(tenant_id,status,created_at);
