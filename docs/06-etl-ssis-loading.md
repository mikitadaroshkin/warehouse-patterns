# ETL and the SSIS loading pattern

The model is only half the work; the other half is loading it reliably, on a
schedule, from source systems that were not built with your warehouse in mind. This
note describes the loading pattern I used in SQL Server Integration Services (SSIS)
years, and then shows the same logic implemented in portable SQL + Python - because
SSIS is a Windows/BIDS runtime and cannot execute in this repo, but its *control
flow* is language-independent and worth writing down.

> Everything here runs on synthetic data. There is no client package, connection,
> or schema anywhere in this repo.

## The shape of a dimensional load

A warehouse load is a sequence, and the order is not negotiable:

1. Extract source data into a staging area, as close to raw as possible.
2. Load dimensions, applying the SCD policy per attribute.
3. Load facts, looking up the (possibly versioned) surrogate keys as you go.

Dimensions before facts, always: a fact row needs its dimension keys to exist and
to be at the right version before it can be resolved.

### How SSIS expresses each step

- Extract -> staging. A *Data Flow* with a source (OLE DB / flat file) into a
  staging table. Staging decouples the load from source availability and lets every
  later step be pure set-based SQL. In this repo the equivalent is the sales extract
  written to a delimited file and bulk-loaded into `stg_sales` with a `COPY`
  (`warehouse_demo/pipeline.py`) - the same "land it as a file, bulk-load it
  columnar" pattern.
- Load a Type-2 dimension. SSIS ships a *Slowly Changing Dimension* transform;
  the wizard generates a Lookup against the current dimension, a *Conditional Split*
  that routes each source row to *new* / *changed* / *unchanged*, and two
  destinations - one that inserts new versions, one that expires superseded ones. At
  volume you replace the wizard with an explicit Lookup + Conditional Split + set-
  based `UPDATE`, because the wizard's row-by-row OLE DB Command does not scale.
  `warehouse_demo/scd.py` is that same decision tree in Python:

  ```
  no current version           -> INSERT a new version 1   (new member)
  current version, no change   -> do nothing               (idempotent)
  current version, changed     -> expire old + INSERT new   (Type-2 change)
  ```

- Load the fact with a key lookup. A *Lookup* per dimension turns each staged
  natural key into a surrogate key, then the row lands in the fact. For a Type-2
  dimension the lookup is point-in-time: match the event date against the
  version's `[valid_from, valid_to)` window so the fact captures the version that
  was current *then*. In this repo that is one set-based join
  (`warehouse_demo/pipeline.py::_resolve_fact`):

  ```sql
  JOIN dim_customer dc ON dc.customer_id = s.customer_id
                      AND s.order_date >= dc.valid_from
                      AND s.order_date <  dc.valid_to
  ```

  Handle the miss explicitly: an unmatched natural key routes to an unknown
  member (a reserved surrogate) rather than dropping the fact row or violating the
  foreign key.

## Idempotency: the property that lets you sleep

A load *will* fail halfway - a source times out, a disk fills, someone kills the
job. The only safe design is one where re-running the load produces the same
result as running it once. Then recovery is "run it again", not a forensic
investigation of what did and did not commit.

Idempotency is a design property, not an afterthought. What buys it:

- Compare before you write. The SCD-2 loader only inserts a new version when a
  *tracked* attribute actually changed. Feed it the same snapshot twice and the
  second pass is a no-op - proven in the demo: re-applying the latest snapshot
  leaves the row count unchanged (`254 -> 254`, all `unchanged`).
- Set-based, deterministic transforms. Prefer `INSERT ... SELECT` and `MERGE`
  over row-by-row procedural logic. A deterministic transform over the same staging
  input yields the same output every time.
- Reload a bounded window, keyed on a business date. Batch loads should be able
  to re-process "everything for order date D" by deleting that window and
  re-inserting it, so a partial failure is cleaned up by simply re-running the
  window rather than hunting for half-written rows.
- Guard the boundaries. Truncate-and-reload staging each run; use the natural
  key plus effective date as the merge key so a replayed row updates in place
  instead of duplicating.

## What this repo implements vs. describes

- Implemented and run on synthetic data: staging bulk-load, the SCD-2 merge, the
  point-in-time surrogate-key lookup into the fact, and an idempotency check - all
  in `warehouse_demo/`, all covered by tests.
- Described (not runnable here): the SSIS Control Flow / Data Flow packages,
  connection managers, and scheduling that would wrap this logic in a SQL Server
  environment. The logic is identical; only the runtime differs.
