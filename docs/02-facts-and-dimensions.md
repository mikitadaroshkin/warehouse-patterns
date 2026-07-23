# Facts and dimensions

Everything in a dimensional model is one of two things: a fact (a measurement
of a business process) or a dimension (the context that gives the measurement
meaning). Getting the split right is most of the job.

## Dimensions: the context

A dimension table answers *who, what, where, when, how*. It is wide, textual, and
comparatively small. Its columns are the things you filter and group by:
`category`, `region`, `segment`, `month_name`. Good dimension design is mostly
about making those attributes rich, readable, and stable:

- Descriptive, decoded values. Store `"Home Office"`, not `3`. The dimension is
  where codes become labels, so reports read in business language and nobody
  memorises a lookup.
- A surrogate key as the primary key, plus the source's natural key as an
  ordinary column (see [grain and surrogate keys](03-grain-and-surrogate-keys.md)).
- Flags and groupings pre-computed. `is_weekend`, `quarter`, a `price_band` -
  put the business logic in the dimension once, not in every query.

`dim_product` in the demo is a plain example: a surrogate `product_key`, the
source `product_id`, and the descriptive attributes `category`, `subcategory`,
`brand`, `unit_price`.

## Facts: the measurements

A fact table holds the numbers. It is narrow, tall, and grows forever. Each row is
one event at a declared [grain](03-grain-and-surrogate-keys.md), and it contains
two kinds of columns only: foreign keys to dimensions, and measures.

```sql
CREATE TABLE fact_sales (
    sale_key      BIGINT PRIMARY KEY,
    order_id      BIGINT NOT NULL,       -- degenerate dimension
    date_key      INTEGER NOT NULL REFERENCES dim_date (date_key),
    product_key   BIGINT NOT NULL REFERENCES dim_product (product_key),
    store_key     BIGINT NOT NULL REFERENCES dim_store (store_key),
    customer_key  BIGINT NOT NULL REFERENCES dim_customer (customer_key),
    quantity      INTEGER NOT NULL,      -- additive
    unit_price    DECIMAL(10, 2) NOT NULL,  -- non-additive (a rate)
    net_amount    DECIMAL(12, 2) NOT NULL   -- additive
);
```

### Additivity is the property that matters

Before a measure goes into a fact, know how it sums:

- Additive - sums correctly across *every* dimension. `quantity`, `net_amount`.
  These are the measures you want; they make every rollup trivially correct.
- Semi-additive - sums across some dimensions but not time. An account balance
  or an inventory level: you sum balances across accounts, but summing a balance
  across days is nonsense; you take an end-of-period snapshot instead.
- Non-additive - never sum. Ratios and rates: `unit_price`, `discount_pct`, a
  margin percentage. Store the *components* (`net_amount`, `cost_amount`) additively
  in the fact and compute the ratio *after* aggregating, never by averaging a
  column of ratios.

The classic bug is `AVG(unit_price)` or `SUM(margin_pct)`. The fix is to store the
additive parts and divide the sums: `SUM(net_amount) / SUM(quantity)`.

### Degenerate dimensions

`order_id` above has no dimension table - there are no interesting attributes of an
order beyond its lines. It rides along on the fact as a *degenerate dimension*, so
you can still group lines back into orders and count distinct orders without a
pointless one-column dimension.

## Fact table flavours

- Transaction fact - one row per event, at the finest grain. The demo's
  `fact_sales` is this: one row per order line. Most flexible; aggregate up to
  anything.
- Periodic snapshot - one row per entity per period (daily inventory, monthly
  balance). This is where semi-additive measures live.
- Accumulating snapshot - one row per long-running process (an order moving
  through pick / pack / ship), with multiple date keys that get filled in as the
  process advances.

Reach for a transaction fact by default. Add a snapshot fact when a question is
naturally about *state at a point in time* rather than *events*.
