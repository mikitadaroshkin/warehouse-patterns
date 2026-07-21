"""Runnable star-schema / dimensional-modelling demo on synthetic data.

The package accompanies the pattern write-ups under ``docs/``. It builds a small
retail-sales star schema in DuckDB, loads deterministic synthetic data, and runs
the analytical queries whose output appears in the README.
"""

from . import pipeline, scd, synthetic

__all__ = ["pipeline", "scd", "synthetic"]
