"""Tests that build the warehouse and assert on real query results.

Everything runs against an in-memory DuckDB built from the synthetic generator,
so the suite is hermetic and fast. The assertions pin down the modelling
guarantees the write-ups claim: correct grain, one current SCD-2 version per
customer, gap-free validity intervals, load idempotency, and the point-in-time
vs. restated attribution behaviour.
"""

import datetime as dt

import duckdb
import pytest

from warehouse_demo import pipeline, synthetic
from warehouse_demo.scd import END_OF_TIME, scd2_upsert


@pytest.fixture(scope="module")
def dataset():
    return synthetic.generate()


@pytest.fixture(scope="module")
def con(dataset):
    # Built once for the module: the demo is read-only for every test except the
    # idempotency check, which is itself a no-op by design.
    connection = duckdb.connect(":memory:")
    pipeline.build(connection, dataset)
    yield connection
    connection.close()


def test_synthetic_generation_is_deterministic():
    a = synthetic.generate()
    b = synthetic.generate()
    assert a.sales == b.sales
    assert a.customer_snapshots == b.customer_snapshots
    assert a.products == b.products


def test_fact_grain_row_count(con, dataset):
    # One fact row per source order line; the as-of customer join must not drop
    # or duplicate any line.
    fact_rows = con.execute("SELECT COUNT(*) FROM fact_sales").fetchone()[0]
    assert fact_rows == len(dataset.sales) == synthetic.N_SALES


def test_every_fact_has_valid_surrogate_keys(con):
    orphans = con.execute(
        """
        SELECT COUNT(*) FROM fact_sales f
        LEFT JOIN dim_customer c ON f.customer_key = c.customer_key
        WHERE c.customer_key IS NULL
        """
    ).fetchone()[0]
    assert orphans == 0


def test_scd2_one_current_version_per_customer(con):
    bad = con.execute(
        """
        SELECT COUNT(*) FROM (
            SELECT customer_id, SUM(CASE WHEN is_current THEN 1 ELSE 0 END) AS n_current
            FROM dim_customer GROUP BY customer_id
        ) WHERE n_current <> 1
        """
    ).fetchone()[0]
    assert bad == 0


def test_scd2_validity_intervals_tile_without_gaps(con):
    # For each customer, ordered by version, valid_to of one row must equal
    # valid_from of the next, and the last row must be open to END_OF_TIME.
    rows = con.execute(
        """
        SELECT customer_id, version, valid_from, valid_to, is_current
        FROM dim_customer ORDER BY customer_id, version
        """
    ).fetchall()
    by_customer: dict[int, list] = {}
    for cid, version, valid_from, valid_to, is_current in rows:
        by_customer.setdefault(cid, []).append((version, valid_from, valid_to, is_current))

    for cid, versions in by_customer.items():
        for i, (_, _, valid_to, is_current) in enumerate(versions):
            if i < len(versions) - 1:
                next_from = versions[i + 1][1]
                assert valid_to == next_from, f"gap for customer {cid}"
                assert not is_current
            else:
                assert valid_to == END_OF_TIME
                assert is_current


def test_scd2_change_produces_new_version(con, dataset):
    # At least one customer changed between the two snapshots, so at least one
    # customer must have two versions.
    multi = con.execute(
        """
        SELECT COUNT(*) FROM (
            SELECT customer_id FROM dim_customer GROUP BY customer_id HAVING COUNT(*) > 1
        )
        """
    ).fetchone()[0]
    assert multi > 0


def test_scd2_load_is_idempotent(con, dataset):
    before = con.execute("SELECT COUNT(*) FROM dim_customer").fetchone()[0]
    as_of, snapshot = dataset.customer_snapshots[-1]
    stats = scd2_upsert(con, snapshot, as_of)
    after = con.execute("SELECT COUNT(*) FROM dim_customer").fetchone()[0]
    assert before == after
    assert stats.inserted == 0
    assert stats.versioned == 0


def test_point_in_time_and_restated_totals_match_but_split_differs(con):
    # The true invariant, on unrounded money: both attributions repartition the
    # exact same fact rows, so each equals the grand total of net_amount.
    grand_total = con.execute("SELECT SUM(net_amount) FROM fact_sales").fetchone()[0]
    total_pit = con.execute(
        """
        SELECT SUM(f.net_amount) FROM fact_sales f
        JOIN dim_customer c ON f.customer_key = c.customer_key
        """
    ).fetchone()[0]
    total_restated = con.execute(
        """
        SELECT SUM(f.net_amount) FROM fact_sales f
        JOIN dim_customer ver ON f.customer_key = ver.customer_key
        JOIN dim_customer cur ON cur.customer_id = ver.customer_id AND cur.is_current
        """
    ).fetchone()[0]
    assert total_pit == grand_total
    assert total_restated == grand_total

    # But per segment the split differs -- that gap is the SCD-2 history a Type-1
    # overwrite would have destroyed.
    _, rows = pipeline.run_query(con, "segment_revenue_pit_vs_current.sql")
    deltas = [r[-1] for r in rows]
    assert any(d != 0 for d in deltas)


def test_category_month_query_covers_all_categories(con):
    columns, rows = pipeline.run_query(con, "category_month_revenue.sql")
    categories = {r[0] for r in rows}
    assert categories == set(synthetic.CATEGORIES)


def test_monthly_trend_reconciles_to_fact_total(con):
    _, rows = pipeline.run_query(con, "monthly_sales_trend.sql")
    order_lines = sum(r[1] for r in rows)
    fact_total = con.execute("SELECT COUNT(*) FROM fact_sales").fetchone()[0]
    assert order_lines == fact_total
