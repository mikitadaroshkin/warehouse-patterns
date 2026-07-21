-- Dimension tables for the retail-sales star schema.
--
-- Conventions used throughout:
--   * Every dimension has a warehouse-generated surrogate key (<dim>_key) that
--     the fact joins on. The source system's natural/business key is kept as a
--     separate column, never used as the join key.
--   * dim_date uses a "smart" integer key (YYYYMMDD). This is the one widely
--     accepted exception to opaque surrogates: it is stable, human-readable in
--     query plans, and lets a fact be partitioned/pruned on date without a join.
--   * dim_customer is modelled as Slowly-Changing-Dimension Type 2: history is
--     preserved as multiple versioned rows per customer_id, bracketed by
--     [valid_from, valid_to) and flagged with is_current.

CREATE TABLE dim_date (
    date_key      INTEGER PRIMARY KEY,   -- YYYYMMDD smart key
    full_date     DATE NOT NULL,
    day_of_month  SMALLINT NOT NULL,
    day_name      VARCHAR NOT NULL,
    day_of_week   SMALLINT NOT NULL,     -- 1 = Monday ... 7 = Sunday
    is_weekend    BOOLEAN NOT NULL,
    month_number  SMALLINT NOT NULL,
    month_name    VARCHAR NOT NULL,
    quarter       SMALLINT NOT NULL,
    year          SMALLINT NOT NULL,
    year_month    VARCHAR NOT NULL       -- 'YYYY-MM', convenient reporting grain
);

CREATE TABLE dim_product (
    product_key   BIGINT PRIMARY KEY,    -- surrogate
    product_id    INTEGER NOT NULL,      -- natural/business key from source
    product_name  VARCHAR NOT NULL,
    category      VARCHAR NOT NULL,
    subcategory   VARCHAR NOT NULL,
    brand         VARCHAR NOT NULL,
    unit_price    DECIMAL(10, 2) NOT NULL
);

CREATE TABLE dim_store (
    store_key     BIGINT PRIMARY KEY,    -- surrogate
    store_id      INTEGER NOT NULL,      -- natural/business key from source
    store_name    VARCHAR NOT NULL,
    city          VARCHAR NOT NULL,
    region        VARCHAR NOT NULL,
    country       VARCHAR NOT NULL
);

-- Surrogate-key generator for the SCD-2 customer dimension. Each new version
-- (a first load or a tracked-attribute change) draws a fresh key.
CREATE SEQUENCE seq_customer_key START 1;

CREATE TABLE dim_customer (
    customer_key  BIGINT PRIMARY KEY DEFAULT nextval('seq_customer_key'),
    customer_id   INTEGER NOT NULL,      -- natural/business key; stable across versions
    first_name    VARCHAR NOT NULL,
    last_name     VARCHAR NOT NULL,
    email         VARCHAR NOT NULL,
    segment       VARCHAR NOT NULL,      -- tracked (Type 2)
    city          VARCHAR NOT NULL,      -- tracked (Type 2)
    region        VARCHAR NOT NULL,      -- tracked (Type 2)
    valid_from    DATE NOT NULL,
    valid_to      DATE NOT NULL,         -- 9999-12-31 while current
    is_current    BOOLEAN NOT NULL,
    version       INTEGER NOT NULL
);
