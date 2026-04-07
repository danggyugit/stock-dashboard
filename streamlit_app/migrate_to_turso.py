"""One-time migration: copy data from local SQLite to Turso.

Usage:
    python migrate_to_turso.py

Reads from data/stock_dashboard.db (local SQLite) and writes to Turso.
Skips Turso connection if not configured in secrets.toml.
"""

import logging
import sqlite3
import sys
from pathlib import Path

import streamlit as st

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

LOCAL_DB = Path(__file__).parent / "data" / "stock_dashboard.db"

# Tables to migrate (skip cache tables to keep migration small)
USER_TABLES = [
    "users",
    "portfolios",
    "trades",
    "watchlist",
    "alerts",
]

CACHE_TABLES = [
    "stocks",
    "fundamentals",
    "daily_prices",
    "fear_greed_history",
    "cache_meta",
]


def main(include_cache: bool = False) -> None:
    if not LOCAL_DB.exists():
        print(f"[FAIL] Local DB not found: {LOCAL_DB}")
        sys.exit(1)

    # Read Turso config
    url = st.secrets.get("turso", {}).get("url")
    token = st.secrets.get("turso", {}).get("auth_token")
    if not url or not token:
        print("[FAIL] Turso config missing in secrets.toml")
        sys.exit(1)

    print(f"[LOCAL] {LOCAL_DB}")
    src = sqlite3.connect(str(LOCAL_DB))
    src.row_factory = sqlite3.Row

    print(f"[TURSO] {url}")
    import libsql
    dst = libsql.connect(database=url, auth_token=token)

    tables = USER_TABLES + (CACHE_TABLES if include_cache else [])

    for table in tables:
        try:
            cols_info = src.execute(f"PRAGMA table_info({table})").fetchall()
        except Exception:
            print(f"[SKIP] {table} (not found in local)")
            continue
        if not cols_info:
            print(f"[SKIP] {table} (no columns)")
            continue
        col_names = [c[1] for c in cols_info]

        rows = src.execute(f"SELECT * FROM {table}").fetchall()
        if not rows:
            print(f"[----] {table}: 0 rows")
            continue

        placeholders = ",".join(["?"] * len(col_names))
        cols_csv = ",".join(col_names)
        sql = f"INSERT OR REPLACE INTO {table} ({cols_csv}) VALUES ({placeholders})"

        success = 0
        for row in rows:
            try:
                dst.execute(sql, tuple(row))
                success += 1
            except Exception as e:
                logger.warning("Failed row in %s: %s", table, e)

        dst.commit()
        print(f"[ OK ] {table}: {success}/{len(rows)} rows migrated")

    print("\nMigration complete.")
    src.close()


if __name__ == "__main__":
    include_cache = "--with-cache" in sys.argv
    main(include_cache=include_cache)
