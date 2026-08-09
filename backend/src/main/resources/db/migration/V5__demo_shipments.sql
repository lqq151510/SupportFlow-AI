CREATE TABLE shipments (
    id BIGINT NOT NULL PRIMARY KEY,
    tenant_id BIGINT NOT NULL,
    customer_id BIGINT NOT NULL,
    order_no VARCHAR(64) NOT NULL,
    tracking_no VARCHAR(64) NOT NULL,
    carrier VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL,
    estimated_delivery_at TIMESTAMP(3) NOT NULL,
    created_at TIMESTAMP(3) NOT NULL,
    CONSTRAINT uk_shipments_tenant_tracking UNIQUE (tenant_id, tracking_no),
    CONSTRAINT fk_shipments_tenant FOREIGN KEY (tenant_id) REFERENCES tenants (id)
);
CREATE INDEX idx_shipments_tenant_customer_order ON shipments (tenant_id, customer_id, order_no);
