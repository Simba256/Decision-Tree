"""
Centralized configuration for Career Decision Tree backend.

Single source of truth for:
  - Database path and connection management
  - Shared baseline financial constants
  - Logging configuration
"""

import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path

# ─── Database ────────────────────────────────────────────────────────────────

DB_PATH = Path(__file__).parent / "career_tree.db"


@contextmanager
def get_db():
    """
    Context-managed database connection.

    Usage:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT ...")

    The connection is automatically closed when the block exits,
    even if an exception occurs.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def get_db_connection():
    """
    Get a raw database connection (caller must close).
    Prefer get_db() context manager when possible.
    Used by modules that load data at import time.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ─── Shared Financial Constants ──────────────────────────────────────────────

# Baseline: current salary (220K PKR/mo ≈ $9.5K/yr)
BASELINE_ANNUAL_SALARY_USD_K = 9.5

# Annual salary growth rate for no-masters baseline path
BASELINE_ANNUAL_GROWTH = 0.08


# ─── Calculator Constants ─────────────────────────────────────────────────────

# Masters path (networth_calculator.py)
MASTERS_TOTAL_YEARS = 12  # 2yr study + 10yr work
MASTERS_DEFAULT_FAMILY_YEAR = 5  # Calendar year when household transitions to family
MASTERS_DEFAULT_DURATION = 2.0  # Default program duration in years

# Career path (career_networth_calculator.py) - stays in Pakistan
CAREER_TOTAL_YEARS = 10
CAREER_DEFAULT_FAMILY_YEAR = 3  # Earlier family transition for Pakistan


# ─── Logging ─────────────────────────────────────────────────────────────────

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level=logging.INFO):
    """Configure logging for the application."""
    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        datefmt=LOG_DATE_FORMAT,
    )


def get_logger(name: str) -> logging.Logger:
    """Get a named logger instance."""
    return logging.getLogger(name)
