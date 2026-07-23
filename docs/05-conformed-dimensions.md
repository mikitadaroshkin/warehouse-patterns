# Conformed dimensions

A dimension is conformed when it means the same thing everywhere it is used. A
conformed `dim_date` or `dim_product` is shared, verbatim, by every fact that
references it - the same keys, the same attributes, the same labels. Conformance is
what turns a collection of separate fact tables into a single warehouse.

## Why it matters

Suppose sales, returns and inventory each live in their own fact table. If all
three share one conformed `dim_product`, then "revenue, returns and stock by
product category" is a well-posed question: you aggregate each fact by the same
`category` attribute and line the answers up. If instead each subject area invented
its own product dimension - one keyed on SKU, one on a marketing code, one spelling
the categories differently - that question becomes a data-reconciliation project.
Every mismatch ("does *Audio* here mean the same as *Audio* there?") is a meeting.

Conformed dimensions are the mechanism behind drill-across: query several facts
independently, each grouped by the shared dimension, then align the results on the
common keys. It only works if the dimension is genuinely identical across facts.

## The bus matrix

The planning tool for this is the bus matrix: business processes (each becomes
a fact) down the rows, conformed dimensions across the columns, a mark where a
process uses a dimension.

| Business process | date | product | store | customer |
|---|:---:|:---:|:---:|:---:|
| Sales            | X | X | X | X |
| Returns          | X | X | X | X |
| Inventory        | X | X | X |   |
| Customer signups | X |   |   | X |

Reading down a column shows which facts must agree on that dimension. Reading
across a row is the design of one fact. The matrix is a one-page contract for the
whole warehouse: build facts incrementally, but commit up front to the shared
dimensions they will all speak.

## Conforming does not mean identical granularity

Two facts can share a dimension at different levels. A daily sales fact joins
`dim_date` at day grain; a monthly forecast fact joins a conformed *month* view of
the same calendar. They still conform, because the month attributes are the same
attributes rolled up - `2025-01` means January 2025 in both. A conformed rollup
is a strict subset of a dimension's attributes at a coarser grain, not a different
dimension.

## In this demo

`dim_date` is the conformed dimension in miniature: `fact_sales` joins it at day
grain, and the monthly-trend and category-by-month queries both group by its
`year_month` attribute. `region` is shared, and identically defined, across
`dim_store` and `dim_customer`, so "revenue by region" means one thing whether you
slice by where the sale happened or where the customer lives. The single-fact demo
does not need a full bus matrix, but the discipline - decide the shared dimensions
first, make every fact speak them - is the same at any scale.
