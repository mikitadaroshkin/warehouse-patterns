#!/usr/bin/env python3
"""Entry point for the star-schema demo.

Builds the schema, loads the synthetic data, and prints the analytical query
output. Optionally persists the warehouse to a DuckDB file for exploration:

    python build_demo.py                 # in-memory, print report
    python build_demo.py warehouse.duckdb  # also persist to a file
"""

import sys

from warehouse_demo.pipeline import main

if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else None
    main(db_path)
