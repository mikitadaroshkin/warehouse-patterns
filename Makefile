.PHONY: setup demo test build clean

# Create a virtualenv and install dependencies.
setup:
	python -m venv .venv
	./.venv/bin/pip install --upgrade pip
	./.venv/bin/pip install -r requirements.txt

# Build the star schema, load synthetic data, print the analytical query output.
demo:
	python build_demo.py

# Same, but persist the warehouse to a DuckDB file you can open and explore.
build:
	python build_demo.py warehouse.duckdb

# Run the test suite (builds an in-memory warehouse and asserts query results).
test:
	python -m pytest tests/ -q

clean:
	rm -f warehouse.duckdb warehouse.duckdb.wal
	rm -rf .pytest_cache **/__pycache__
