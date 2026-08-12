ALTER TABLE tickets ADD COLUMN claim_idempotency_key VARCHAR(128);
CREATE UNIQUE INDEX uk_ticket_claim_idempotency
    ON tickets(tenant_id, assigned_membership_id, claim_idempotency_key);
