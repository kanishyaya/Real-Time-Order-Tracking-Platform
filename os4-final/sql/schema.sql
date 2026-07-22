-- ============================================================
--  Schema: Real-Time Order Tracking System
--  Creates the orders table and the event log table.
-- ============================================================


-- Orders table (as per assignment spec)
CREATE TABLE IF NOT EXISTS orders (
    id              SERIAL PRIMARY KEY,
    customer_name   TEXT        NOT NULL,
    product_name    TEXT        NOT NULL,
    status          TEXT        NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'shipped', 'delivered')),
    updated_at      TIMESTAMP   NOT NULL DEFAULT NOW()
);


-- Event log table — stores every DB change for replay on reconnect
CREATE TABLE IF NOT EXISTS order_events (
    id          SERIAL      PRIMARY KEY,
    operation   TEXT        NOT NULL,       -- INSERT | UPDATE | DELETE
    order_id    INTEGER     NOT NULL,
    payload     JSONB       NOT NULL,
    occurred_at TIMESTAMP   NOT NULL DEFAULT NOW()
);


-- Index for efficient event replay queries
CREATE INDEX IF NOT EXISTS idx_order_events_occurred_at
    ON order_events (occurred_at DESC);
