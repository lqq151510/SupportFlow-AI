CREATE TABLE orders (
    id BIGINT NOT NULL PRIMARY KEY,
    tenant_id BIGINT NOT NULL,
    customer_id BIGINT NOT NULL,
    order_no VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL,
    total_amount DECIMAL(12, 2) NOT NULL,
    currency CHAR(3) NOT NULL,
    created_at TIMESTAMP(3) NOT NULL,
    updated_at TIMESTAMP(3) NOT NULL,
    CONSTRAINT uk_orders_tenant_order_no UNIQUE (tenant_id, order_no),
    CONSTRAINT fk_orders_tenant FOREIGN KEY (tenant_id) REFERENCES tenants (id),
    CONSTRAINT fk_orders_customer FOREIGN KEY (customer_id) REFERENCES users (id)
);

CREATE INDEX idx_orders_tenant_customer_created ON orders (tenant_id, customer_id, created_at DESC);
