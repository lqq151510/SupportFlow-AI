CREATE TABLE ticket_comments (
 id BIGINT NOT NULL PRIMARY KEY, tenant_id BIGINT NOT NULL, ticket_id BIGINT NOT NULL, author_membership_id BIGINT NOT NULL, content LONGTEXT NOT NULL, created_at TIMESTAMP(3) NOT NULL,
 CONSTRAINT fk_ticket_comments_ticket FOREIGN KEY (ticket_id) REFERENCES tickets(id));
CREATE INDEX idx_ticket_comments_ticket ON ticket_comments(tenant_id,ticket_id,created_at);
