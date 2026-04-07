"""Database layer with dual backend support: SQLite (local) + Turso (cloud).

If Streamlit secrets contain `[turso] url + auth_token`, use Turso (libsql).
Otherwise fall back to local SQLite file.
"""

import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

_DB_PATH = Path(__file__).parent / "data" / "stock_dashboard.db"
_conn = None
_backend = "sqlite"  # or "turso"


def _get_turso_config() -> tuple[str | None, str | None]:
    """Read Turso config from Streamlit secrets if available."""
    try:
        import streamlit as st
        url = st.secrets.get("turso", {}).get("url")
        token = st.secrets.get("turso", {}).get("auth_token")
        return url, token
    except Exception:
        return None, None


def get_connection():
    """Return a singleton DB connection. Uses Turso if configured, else SQLite."""
    global _conn, _backend
    if _conn is not None:
        return _conn

    url, token = _get_turso_config()
    if url and token:
        try:
            import libsql
            _conn = libsql.connect(database=url, auth_token=token)
            _backend = "turso"
            logger.info("Connected to Turso: %s", url)
            return _conn
        except Exception as e:
            logger.exception("Turso connection failed, falling back to SQLite: %s", e)

    # SQLite fallback
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    _conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    _conn.execute("PRAGMA journal_mode=WAL")
    _conn.execute("PRAGMA foreign_keys=ON")
    _conn.row_factory = sqlite3.Row
    _backend = "sqlite"
    logger.info("Connected to SQLite: %s", _DB_PATH)
    return _conn


def get_backend() -> str:
    """Return current backend name ('sqlite' or 'turso')."""
    return _backend


# --- Schema definitions (split into individual statements for libsql compat) ---

_SCHEMA_STATEMENTS = [
    """CREATE TABLE IF NOT EXISTS users (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        google_sub  TEXT UNIQUE,
        email       TEXT UNIQUE NOT NULL,
        name        TEXT,
        picture     TEXT,
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_login  TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS stocks (
        ticker       TEXT PRIMARY KEY,
        name         TEXT NOT NULL,
        sector       TEXT,
        industry     TEXT,
        market_cap   INTEGER,
        exchange     TEXT,
        updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS daily_prices (
        ticker  TEXT NOT NULL,
        date    TEXT NOT NULL,
        open    REAL,
        high    REAL,
        low     REAL,
        close   REAL,
        volume  INTEGER,
        PRIMARY KEY (ticker, date)
    )""",
    """CREATE TABLE IF NOT EXISTS fundamentals (
        ticker              TEXT PRIMARY KEY,
        pe_ratio            REAL,
        pb_ratio            REAL,
        ps_ratio            REAL,
        eps                 REAL,
        roe                 REAL,
        debt_to_equity      REAL,
        dividend_yield      REAL,
        beta                REAL,
        fifty_two_week_high REAL,
        fifty_two_week_low  REAL,
        avg_volume          INTEGER,
        updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS dividends (
        ticker       TEXT NOT NULL,
        ex_date      TEXT NOT NULL,
        payment_date TEXT,
        amount       REAL,
        PRIMARY KEY (ticker, ex_date)
    )""",
    """CREATE TABLE IF NOT EXISTS portfolios (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER,
        name        TEXT NOT NULL,
        description TEXT,
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS trades (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        portfolio_id INTEGER NOT NULL,
        ticker       TEXT NOT NULL,
        trade_type   TEXT NOT NULL,
        quantity     REAL NOT NULL,
        price        REAL NOT NULL,
        commission   REAL DEFAULT 0,
        trade_date   TEXT NOT NULL,
        note         TEXT,
        created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS economic_events (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        event_name  TEXT NOT NULL,
        country     TEXT DEFAULT 'US',
        event_date  TEXT NOT NULL,
        event_time  TEXT,
        actual      REAL,
        forecast    REAL,
        previous    REAL,
        importance  TEXT DEFAULT 'medium',
        unit        TEXT,
        cached_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS earnings_calendar (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker           TEXT NOT NULL,
        company_name     TEXT,
        earnings_date    TEXT NOT NULL,
        eps_estimate     REAL,
        eps_actual       REAL,
        revenue_estimate REAL,
        revenue_actual   REAL,
        cached_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS news_articles (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker          TEXT,
        headline        TEXT NOT NULL,
        summary         TEXT,
        source          TEXT,
        url             TEXT,
        published_at    TEXT,
        sentiment       REAL,
        sentiment_label TEXT,
        ai_summary      TEXT,
        analyzed_at     TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS fear_greed_history (
        date           TEXT PRIMARY KEY,
        score          REAL,
        label          TEXT,
        vix_score      REAL,
        momentum_score REAL,
        put_call_score REAL,
        high_low_score REAL,
        volume_score   REAL
    )""",
    """CREATE TABLE IF NOT EXISTS daily_reports (
        date         TEXT PRIMARY KEY,
        content      TEXT,
        generated_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS watchlist (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER,
        ticker      TEXT NOT NULL,
        note        TEXT,
        added_price REAL,
        added_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (user_id, ticker)
    )""",
    """CREATE TABLE IF NOT EXISTS alerts (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER,
        ticker      TEXT NOT NULL,
        condition   TEXT NOT NULL,
        threshold   REAL NOT NULL,
        note        TEXT,
        active      INTEGER DEFAULT 1,
        triggered   INTEGER DEFAULT 0,
        triggered_at TIMESTAMP,
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS cache_meta (
        key         TEXT PRIMARY KEY,
        updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
]


def init_db() -> None:
    """Initialize database with all required tables (works on both backends)."""
    conn = get_connection()

    # Create all tables
    for stmt in _SCHEMA_STATEMENTS:
        try:
            conn.execute(stmt)
        except Exception as e:
            logger.warning("Failed to create table: %s", e)

    # ALTER existing tables to add user_id (idempotent, for SQLite migration)
    for table in ("portfolios", "watchlist", "alerts"):
        try:
            conn.execute(f"SELECT user_id FROM {table} LIMIT 0")
        except Exception:
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN user_id INTEGER")
                logger.info("Added user_id column to %s", table)
            except Exception:
                pass

    conn.commit()
    logger.info("Database initialized (backend: %s)", _backend)
