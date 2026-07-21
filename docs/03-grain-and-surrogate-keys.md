# Grain and surrogate keys

## Declare the grain first

The **grain** is the answer to "what does one row of the fact mean?" — stated in
business terms, before a single column is chosen. For the demo:

> One row of `fact_sales` = one product line on one sales order.

Everything downstream is determined by that sentence. The grain fixes:

- **Dimensionality.** "One product line on one order" implies a product, a store,
  a customer, and a date. Those are the fact's foreign keys, and no others.
- **Additivity.** Measures only make sense relative to the grain. `quantity` is the
  quantity *of that line*; it is additive because line-level quantities sum cleanly
  to order, day, month, and year totals.
- **What you can and cannot ask.** At line grain you can roll up to anything coarser
  (order, day, category, region). You can never drill *below* the declared grain —
  if you did not capture it per line, it is gone.

Two rules follow, and violating either is the source of most fact-table bugs:

1. **Every row is at the same grain.** Never mix an order-line row with an
   order-total row in the same table. Totals are derived at query time, not stored
   as extra rows — otherwise every `SUM` double-counts.
2. **Pick the finest grain you can afford.** Fine grain is future-proof: you can
   always aggregate up, never down. Pre-aggregated facts are an optimisation you
   add *later*, alongside the atomic fact, not instead of it.

A useful test: if a stakeholder asks a question your fact cannot answer, it is
almost always because the grain was too coarse. Line grain answers "what was the
average discount on Electronics lines in March?"; an order-total grain cannot.

## Surrogate keys

A **surrogate key** is a meaningless, warehouse-generated integer that is the
primary key of a dimension. The fact joins on it. The source system's own
identifier — the **natural** or **business** key — is kept as an ordinary column.

```sql
CREATE TABLE dim_product (
    product_key   BIGINT PRIMARY KEY,   -- surrogate: the warehouse's own key
    product_id    INTEGER NOT NULL,     -- natural key: the source system's id
    ...
);
```

Why not just join the fact on `product_id`?

- **The natural key is not yours to control.** Source systems reuse ids, re-key
  during migrations, merge two products into one, or hand you a composite key that
  changes shape. A surrogate insulates the fact from all of that: the source can do
  what it likes and your keys stay stable.
- **Slowly-changing dimensions require it.** Type-2 history means *many* dimension
  rows share one natural key — one per version (see
  [slowly-changing dimensions](04-slowly-changing-dimensions.md)). The natural key
  is therefore no longer unique in the dimension and cannot be the join key. The
  surrogate identifies a specific *version*, which is exactly what a fact row needs
  to point at.
- **Joins are faster and narrower.** A single integer key beats a wide or composite
  natural key on both join performance and fact-table width.
- **It gives you an unknown member.** Reserve a surrogate (e.g. key `-1` /
  `"Unknown"`) so a fact with a missing or late-arriving dimension value still
  joins, instead of being dropped by an inner join or breaking referential
  integrity.

### The one accepted exception: the date key

`dim_date` uses a *smart* integer key `YYYYMMDD` (`20250131`) rather than an opaque
surrogate. This is the standard, deliberate exception:

- dates never change, re-key, or get merged, so the reasons for opacity do not apply;
- the key is human-readable in query plans and data (`20250131` needs no join to
  interpret);
- a fact can be range-partitioned or pruned on `date_key` directly, without joining
  `dim_date` at all.

Everywhere else, keep surrogates opaque. A key should carry no meaning precisely so
that changing the meaning of the thing it identifies never forces you to change the
key.
