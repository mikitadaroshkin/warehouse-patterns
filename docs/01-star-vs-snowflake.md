# Star vs. snowflake

The star schema is the default shape for an analytical model, and it earns that
default. A single fact table sits in the middle; each dimension is one flat table
joined to the fact by a surrogate key. A query answers a business question by
picking the fact, filtering and grouping on dimension attributes, and aggregating
the fact's measures. Nothing else.

```
        dim_date            dim_product
             \                  /
              \                /
   dim_store --- fact_sales --- dim_customer
```

The snowflake schema takes the same star and *normalises* the dimensions:
repeating attributes are lifted into their own tables. `dim_product` stops
carrying `category` and `subcategory` as text and instead points at a
`dim_category` row, which may in turn point at a `dim_department` row.

```
dim_department --- dim_category --- dim_product --- fact_sales
```

## Why star is the default

- **Fewer joins.** Every dimension is one hop from the fact. A category rollup is
  `fact JOIN dim_product` and a `GROUP BY category`. In a snowflake it becomes
  `fact JOIN dim_product JOIN dim_category`, and department is a third join. Join
  count is the thing analysts and BI tools trip over most.
- **It matches how BI tools think.** Tableau, Power BI, Looker and the like model
  a star natively — one fact, dimensions hanging off it. Hand them a snowflake and
  you spend your time hiding bridge tables from users.
- **Storage is not the constraint.** The classic argument for snowflaking is that
  storing `"Electronics"` on ten thousand product rows wastes space. On columnar
  analytical engines that string is dictionary-encoded to a small integer anyway,
  so the redundancy costs almost nothing. You are trading a real query-time cost
  (extra joins) for an imaginary storage saving.

## When a snowflake is the right call

Normalising a branch of a dimension is justified when:

- **The sub-entity has real, independent life.** If a `category` carries its own
  attributes that are maintained separately (a category manager, a margin target,
  a seasonal flag) and is referenced by things other than products, promoting it
  to its own dimension keeps that master data in one place.
- **A dimension is genuinely huge and highly repetitive.** A hundred-million-row
  dimension with a large, slowly-changing normalised branch can be cheaper to
  maintain snowflaked, because a change to the branch touches one row instead of
  millions.
- **You need a hierarchy as a first-class object** for a bridge or ragged-hierarchy
  pattern that a flat dimension cannot express cleanly.

## The pragmatic middle: outriggers

You do not have to choose globally. A *star with outriggers* keeps dimensions flat
but factors out a shared sub-dimension where it genuinely helps — a `dim_date`
referenced from several dimensions, for instance. Snowflake exactly where the
master data demands it, and leave everything else flat.

## Rule of thumb

Model a star. Snowflake a specific branch only when a concrete master-data or
scale problem forces it, and be able to name that problem. "It felt tidier to
normalise" is not that problem — tidiness in an analytical model is measured in
join count at query time, not in third normal form.

The demo in this repo is deliberately a clean star: `category` and `subcategory`
live as columns on `dim_product`, and `region` lives on both `dim_store` and
`dim_customer` rather than in a separate geography table.
