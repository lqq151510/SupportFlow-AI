CREATE TABLE event_outbox (
 id BIGINT NOT NULL PRIMARY KEY, tenant_id BIGINT NOT NULL, event_type VARCHAR(128) NOT NULL, aggregate_type VARCHAR(64) NOT NULL, aggregate_id VARCHAR(64) NOT NULL, payload CLOB NOT NULL, status VARCHAR(32) NOT NULL, attempt_count INT NOT NULL DEFAULT 0, created_at TIMESTAMP(3) NOT NULL, published_at TIMESTAMP(3));
CREATE TABLE consumed_events (
 id BIGINT NOT NULL PRIMARY KEY, consumer_name VARCHAR(128) NOT NULL, event_id BIGINT NOT NULL, processed_at TIMESTAMP(3) NOT NULL,
 CONSTRAINT uk_consumed_events_consumer_event UNIQUE (consumer_name,event_id));
CREATE INDEX idx_event_outbox_status ON event_outbox(status,created_at);
