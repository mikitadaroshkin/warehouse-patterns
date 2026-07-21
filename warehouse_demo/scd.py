"""Slowly-Changing-Dimension Type-2 loader.

This is the reusable piece of the ETL: the merge that turns a stream of source
snapshots into a versioned dimension. It is written to be *idempotent* -- feeding
the same snapshot twice must not create a second version -- because idempotency
is what makes a warehouse load safe to re-run after a failure.

The classic SSIS implementation of this is the *Slowly Changing Dimension*
transform (or, at scale, a Lookup + Conditional Split + two OLE DB
Destinations). SSIS is a Windows/BIDS runtime and cannot execute in this repo,
so the same decision logic is expressed here in portable Python + SQL. The
control flow is deliberately the same one the SSIS wizard generates:

    for each source row, keyed by the natural key:
        no current version           -> INSERT a new version 1        (new member)
        current version, no change   -> do nothing                    (idempotent)
        current version, changed     -> expire the old version and
                                        INSERT a new current version  (Type-2 change)
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

# Attributes whose change opens a new version. Everything else is treated as
# descriptive and stable (a real model would load those as Type 1 in place).
TRACKED_ATTRIBUTES = ("segment", "city", "region")

# Sentinel high date for the open end of the current version's validity window.
END_OF_TIME = dt.date(9999, 12, 31)


@dataclass
class LoadStats:
    """What a single snapshot load did -- handy for logs, tests and the README."""

    inserted: int = 0   # brand-new customers (version 1)
    versioned: int = 0  # existing customers whose tracked attributes changed
    unchanged: int = 0   # existing customers with no tracked change (no-op)

    def as_dict(self) -> dict[str, int]:
        return {"inserted": self.inserted, "versioned": self.versioned, "unchanged": self.unchanged}


def _current_rows(con) -> dict[int, dict]:
    """Return the current version of every customer, keyed by natural key."""

    cols = ["customer_id", "version", *TRACKED_ATTRIBUTES]
    rows = con.execute(
        f"SELECT {', '.join(cols)} FROM dim_customer WHERE is_current"
    ).fetchall()
    return {row[0]: dict(zip(cols, row)) for row in rows}


def _tracked_changed(current: dict, source: dict) -> bool:
    return any(current[attr] != source[attr] for attr in TRACKED_ATTRIBUTES)


def scd2_upsert(con, source_rows: list[dict], as_of: dt.date) -> LoadStats:
    """Merge one source snapshot into ``dim_customer`` as SCD Type 2.

    ``con`` is a DuckDB connection whose schema already contains ``dim_customer``
    and the ``seq_customer_key`` sequence. ``as_of`` is the effective date of the
    snapshot: expiring versions close at ``as_of`` and new versions open at it, so
    the [valid_from, valid_to) intervals tile the timeline with no gaps or
    overlaps.
    """

    current = _current_rows(con)
    stats = LoadStats()

    to_expire: list[tuple[dt.date, int]] = []          # (as_of, customer_id)
    to_insert: list[tuple] = []                          # new version rows

    for src in source_rows:
        cid = src["customer_id"]
        existing = current.get(cid)

        if existing is None:
            to_insert.append(_new_version_row(src, as_of, version=1))
            stats.inserted += 1
        elif _tracked_changed(existing, src):
            to_expire.append((as_of, cid))
            to_insert.append(_new_version_row(src, as_of, version=existing["version"] + 1))
            stats.versioned += 1
        else:
            stats.unchanged += 1

    # Expire superseded versions in one set-based statement.
    if to_expire:
        con.executemany(
            "UPDATE dim_customer SET valid_to = ?, is_current = FALSE "
            "WHERE customer_id = ? AND is_current",
            to_expire,
        )

    # Insert the new versions. customer_key is drawn from the sequence DEFAULT.
    if to_insert:
        con.executemany(
            "INSERT INTO dim_customer "
            "(customer_id, first_name, last_name, email, segment, city, region, "
            " valid_from, valid_to, is_current, version) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, TRUE, ?)",
            to_insert,
        )

    return stats


def _new_version_row(src: dict, as_of: dt.date, version: int) -> tuple:
    return (
        src["customer_id"],
        src["first_name"],
        src["last_name"],
        src["email"],
        src["segment"],
        src["city"],
        src["region"],
        as_of,
        END_OF_TIME,
        version,
    )
