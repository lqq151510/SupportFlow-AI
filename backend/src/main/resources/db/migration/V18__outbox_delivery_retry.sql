ALTER TABLE event_outbox ADD COLUMN next_attempt_at TIMESTAMP(3);
ALTER TABLE event_outbox ADD COLUMN last_error VARCHAR(500);
ALTER TABLE event_outbox ADD COLUMN failed_at TIMESTAMP(3);
UPDATE event_outbox SET next_attempt_at = created_at WHERE status = 'PENDING';
CREATE INDEX idx_event_outbox_retry ON event_outbox(status, next_attempt_at);
