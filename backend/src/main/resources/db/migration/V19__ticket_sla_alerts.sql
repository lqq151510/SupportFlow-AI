CREATE TABLE ticket_sla_alerts (
 id BIGINT NOT NULL PRIMARY KEY,
 tenant_id BIGINT NOT NULL,
 ticket_id BIGINT NOT NULL,
 alert_type VARCHAR(32) NOT NULL,
 due_at TIMESTAMP(3) NOT NULL,
 alerted_at TIMESTAMP(3) NOT NULL,
 CONSTRAINT uk_ticket_sla_alert UNIQUE (tenant_id, ticket_id, alert_type)
);
CREATE INDEX idx_ticket_sla_alerts_ticket ON ticket_sla_alerts(tenant_id, ticket_id);
