"""Build the retail-sales star schema and run the analytical queries.

This is the demo runner. It creates the schema from the DDL under ``sql/``,
loads the synthetic data, applies the SCD-2 customer load, resolves surrogate
keys into the fact (including the point-in-time customer key), and executes the
analytics queries under ``sql/analytics/``. Every number the README quotes comes
out of ``main()`` here -- nothing is hand-written.
"""

from __future__ import annotations

import csv
import datetime as dt
import tempfile
from pathlib import Path

import duckdb

from . import synthetic
from .scd import scd2_upsert

REPO_ROOT = Path(__file__).resolve().parent.parent
SQL_DIR = REPO_ROOT / "sql"
ANALYTICS_DIR = SQL_DIR / "analytics"

# Analytics queries surfaced in the report / README, in display order.
ANALYTICS_QUERIES = [
    ("Net revenue by category by month (H1 2025)", "category_month_revenue.sql"),
    ("Monthly sales trend (whole fact)", "monthly_sales_trend.sql"),
    ("SCD-2 customer version history", "scd2_customer_history.sql"),
    ("Segment revenue: point-in-time vs. restated-to-current", "segment_revenue_pit_vs_current.sql"),
]


def _load_dim_date(con: duckdb.DuckDBPyConnection, start: dt.date, end: dt.date) -> None:
    # The calendar is generated in-engine from a day range (see the SQL file).
    con.execute((SQL_DIR / "03_load_dim_date.sql").read_text(), [start, end])


def _load_dim_product(con: duckdb.DuckDBPyConnection, products: list[dict]) -> None:
    rows = [
        (
            i + 1,  # surrogate product_key
            p["product_id"],
            p["product_name"],
            p["category"],
            p["subcategory"],
            p["brand"],
            p["unit_price"],
        )
        for i, p in enumerate(products)
    ]
    con.executemany("INSERT INTO dim_product VALUES (?, ?, ?, ?, ?, ?, ?)", rows)


def _load_dim_store(con: duckdb.DuckDBPyConnection, stores: list[dict]) -> None:
    rows = [
        (
            i + 1,  # surrogate store_key
            s["store_id"],
            s["store_name"],
            s["city"],
            s["region"],
            s["country"],
        )
        for i, s in enumerate(stores)
    ]
    con.executemany("INSERT INTO dim_store VALUES (?, ?, ?, ?, ?, ?)", rows)


STG_COLUMNS = [
    "order_id", "order_date", "product_id", "store_id", "customer_id",
    "quantity", "unit_price", "discount_pct", "gross_amount", "net_amount",
]


def _load_stg_sales(con: duckdb.DuckDBPyConnection, sales: list[dict]) -> None:
    """Bulk-load the sales extract into staging via a file COPY.

    This mirrors how a warehouse actually stages source data: the extract lands
    as a delimited file and the engine bulk-loads it columnar-fast, rather than
    row-by-row INSERTs. The file is written to a temp path and removed after.
    """

    with tempfile.NamedTemporaryFile("w", suffix=".csv", newline="", delete=False) as fh:
        writer = csv.writer(fh)
        writer.writerow(STG_COLUMNS)
        for s in sales:
            writer.writerow([s[col] for col in STG_COLUMNS])
        extract_path = fh.name
    try:
        con.execute(
            f"COPY stg_sales FROM '{extract_path}' (HEADER, DATEFORMAT '%Y-%m-%d')"
        )
    finally:
        Path(extract_path).unlink(missing_ok=True)


def _resolve_fact(con: duckdb.DuckDBPyConnection) -> None:
    """Load fact_sales from staging, resolving surrogate keys.

    The customer join is an *as-of* join against the SCD-2 validity window, so a
    sale is stamped with the customer version that was current on its order date
    -- the point-in-time surrogate-key lookup at the heart of a Kimball load.
    """

    con.execute(
        """
        INSERT INTO fact_sales
        SELECT
            ROW_NUMBER() OVER (ORDER BY s.order_id)                            AS sale_key,
            s.order_id,
            year(s.order_date) * 10000 + month(s.order_date) * 100
                + day(s.order_date)                                           AS date_key,
            dp.product_key,
            ds.store_key,
            dc.customer_key,
            s.quantity, s.unit_price, s.discount_pct, s.gross_amount, s.net_amount
        FROM stg_sales s
        JOIN dim_product  dp ON dp.product_id  = s.product_id
        JOIN dim_store    ds ON ds.store_id    = s.store_id
        JOIN dim_customer dc ON dc.customer_id = s.customer_id
                            AND s.order_date >= dc.valid_from
                            AND s.order_date <  dc.valid_to
        """
    )


def build(con: duckdb.DuckDBPyConnection, dataset: synthetic.Dataset | None = None) -> dict:
    """Create the schema, load everything, return load statistics."""

    if dataset is None:
        dataset = synthetic.generate()

    con.execute((SQL_DIR / "01_dimensions.sql").read_text())
    con.execute((SQL_DIR / "02_fact.sql").read_text())

    _load_dim_product(con, dataset.products)
    _load_dim_store(con, dataset.stores)
    _load_dim_date(con, synthetic.SALES_START, synthetic.SALES_END)

    # Apply the customer snapshots oldest-first as SCD Type 2.
    scd_stats = []
    for as_of, snapshot in dataset.customer_snapshots:
        scd_stats.append((as_of, scd2_upsert(con, snapshot, as_of).as_dict()))

    _load_stg_sales(con, dataset.sales)
    _resolve_fact(con)

    return {
        "products": len(dataset.products),
        "stores": len(dataset.stores),
        "customer_versions": con.execute("SELECT COUNT(*) FROM dim_customer").fetchone()[0],
        "customers": con.execute(
            "SELECT COUNT(DISTINCT customer_id) FROM dim_customer"
        ).fetchone()[0],
        "fact_rows": con.execute("SELECT COUNT(*) FROM fact_sales").fetchone()[0],
        "scd_loads": scd_stats,
    }


def idempotency_check(con: duckdb.DuckDBPyConnection, dataset: synthetic.Dataset) -> dict:
    """Re-apply the latest snapshot; a correct SCD-2 load must be a no-op."""

    before = con.execute("SELECT COUNT(*) FROM dim_customer").fetchone()[0]
    as_of, snapshot = dataset.customer_snapshots[-1]
    stats = scd2_upsert(con, snapshot, as_of).as_dict()
    after = con.execute("SELECT COUNT(*) FROM dim_customer").fetchone()[0]
    return {"rows_before": before, "rows_after": after, "load_stats": stats}


def run_query(con: duckdb.DuckDBPyConnection, filename: str) -> tuple[list[str], list[tuple]]:
    sql = (ANALYTICS_DIR / filename).read_text()
    cur = con.execute(sql)
    columns = [d[0] for d in cur.description]
    return columns, cur.fetchall()


# --- console formatting ----------------------------------------------------
def format_table(columns: list[str], rows: list[tuple]) -> str:
    widths = [len(c) for c in columns]
    str_rows = []
    for row in rows:
        cells = ["" if v is None else str(v) for v in row]
        str_rows.append(cells)
        widths = [max(w, len(c)) for w, c in zip(widths, cells)]
    line = " | ".join(c.ljust(w) for c, w in zip(columns, widths))
    sep = "-+-".join("-" * w for w in widths)
    body = "\n".join(" | ".join(c.ljust(w) for c, w in zip(cells, widths)) for cells in str_rows)
    return f"{line}\n{sep}\n{body}"


def main(db_path: str | None = None) -> None:
    con = duckdb.connect(db_path or ":memory:")
    dataset = synthetic.generate()
    stats = build(con, dataset)

    print("=" * 78)
    print("warehouse-patterns :: retail-sales star-schema demo (synthetic data)")
    print("=" * 78)
    print(
        f"loaded  products={stats['products']}  stores={stats['stores']}  "
        f"customers={stats['customers']}  customer_versions={stats['customer_versions']}  "
        f"fact_rows={stats['fact_rows']}"
    )
    print("\nSCD-2 customer load (per source snapshot):")
    for as_of, load in stats["scd_loads"]:
        print(
            f"  as_of {as_of}:  inserted={load['inserted']:<4} "
            f"versioned={load['versioned']:<4} unchanged={load['unchanged']:<4}"
        )

    idem = idempotency_check(con, dataset)
    print(
        f"\nidempotency re-run of last snapshot:  rows {idem['rows_before']} -> "
        f"{idem['rows_after']}  (load {idem['load_stats']})"
    )

    for title, filename in ANALYTICS_QUERIES:
        columns, rows = run_query(con, filename)
        print(f"\n### {title}\n-- sql/analytics/{filename}")
        print(format_table(columns, rows))

    con.close()


if __name__ == "__main__":
    main()
