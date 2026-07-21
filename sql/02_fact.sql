-- Fact table for the retail-sales star schema.
--
-- Grain: exactly one row per sales order line (one product on one order). The
-- grain is stated first because every other modelling decision follows from it:
-- the dimensionality (date, product, store, customer) and which measures are
-- additive are only well-defined once the grain is fixed.
--
-- Measures:
--   quantity, gross_amount, net_amount  -- fully additive across every dimension
--   unit_price                          -- non-additive (a rate); never SUM it
--   discount_pct                        -- non-additive (a ratio); never SUM it
--
-- order_id is a degenerate dimension: a business identifier that lives on the
-- fact with no dimension table of its own, so order-level rollups stay possible.

-- Landing/staging table. The raw extract lands here with natural keys and the
-- event date, then a set-based lookup resolves surrogate keys on the way into
-- the fact -- including the *point-in-time* customer_key for the SCD-2 join.
CREATE TABLE stg_sales (
    order_id      BIGINT NOT NULL,
    order_date    DATE NOT NULL,
    product_id    INTEGER NOT NULL,
    store_id      INTEGER NOT NULL,
    customer_id   INTEGER NOT NULL,
    quantity      INTEGER NOT NULL,
    unit_price    DECIMAL(10, 2) NOT NULL,
    discount_pct  DECIMAL(5, 4) NOT NULL,
    gross_amount  DECIMAL(12, 2) NOT NULL,
    net_amount    DECIMAL(12, 2) NOT NULL
);

CREATE TABLE fact_sales (
    sale_key      BIGINT PRIMARY KEY,
    order_id      BIGINT NOT NULL,       -- degenerate dimension
    date_key      INTEGER NOT NULL REFERENCES dim_date (date_key),
    product_key   BIGINT NOT NULL REFERENCES dim_product (product_key),
    store_key     BIGINT NOT NULL REFERENCES dim_store (store_key),
    customer_key  BIGINT NOT NULL REFERENCES dim_customer (customer_key),
    quantity      INTEGER NOT NULL,
    unit_price    DECIMAL(10, 2) NOT NULL,
    discount_pct  DECIMAL(5, 4) NOT NULL,
    gross_amount  DECIMAL(12, 2) NOT NULL,
    net_amount    DECIMAL(12, 2) NOT NULL
);
