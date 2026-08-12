CREATE TABLE ticket_assignments (
    id BIGINT PRIMARY KEY,
    tenant_id BIGINT NOT NULL,
    ticket_id BIGINT NOT NULL,
    from_membership_id BIGINT,
    to_membership_id BIGINT NOT NULL,
    assigned_by_membership_id BIGINT NOT NULL,
    created_at TIMESTAMP(6) NOT NULL,
    CONSTRAINT fk_ticket_assignment_ticket FOREIGN KEY (ticket_id) REFERENCES tickets(id),
    CONSTRAINT fk_ticket_assignment_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

CREATE INDEX idx_ticket_assignment_audit ON ticket_assignments(tenant_id, ticket_id, created_at);
