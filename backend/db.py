"""DuckDB connection management with singleton pattern.

Handles database initialization, table creation, and connection lifecycle.
All table schemas follow the TRD specification.
"""

import logging
import threading
from pathlib import Path

import duckdb

from config import get_settings

logger = logging.getLogger(__name__)

_local = threading.local()
_db_path: str | None = None
_db_lock = threading.Lock()


def get_connection() -> duckdb.DuckDBPyConnection:
    """Return a thread-local DuckDB connection.

    Each thread gets its own connection to avoid concurrency issues
    between API handlers and background scheduler threads.

    Returns:
        DuckDBPyConnection: Active database connection for this thread.
    """
    global _db_path  # noqa: PLW0603

    if _db_path is None:
        with _db_lock:
            if _db_path is None:
                settings = get_settings()
                db_path = Path(settings.DUCKDB_PATH)
                db_path.parent.mkdir(parents=True, exist_ok=True)
                _db_path = str(db_path)

    conn = getattr(_local, "connection", None)
    if conn is None:
        conn = duckdb.connect(_db_path)
        _local.connection = conn
        logger.info("DuckDB connection established for thread %s", threading.current_thread().name)
    return conn


def init_db() -> None:
    """Initialize database with all required tables and sequences.

    Creates tables and sequences as defined in the TRD if they don't
    already exist. Safe to call multiple times.
    """
    conn = get_connection()

    # --- Users Table ---
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id           INTEGER PRIMARY KEY,
            google_id    VARCHAR UNIQUE,
            email        VARCHAR UNIQUE NOT NULL,
            name         VARCHAR,
            avatar_url   VARCHAR,
            created_at   TIMESTAMP DEFAULT current_timestamp
        )
    """)
    _create_sequence_if_not_exists(conn, "seq_user_id")

    # Add user_id to portfolios if not exists
    try:
        conn.execute("SELECT user_id FROM portfolios LIMIT 0")
    except Exception:
        try:
            conn.execute("ALTER TABLE portfolios ADD COLUMN user_id INTEGER")
            logger.info("Added user_id column to portfolios table.")
        except Exception:
            pass

    # --- Market Data Tables ---
    conn.execute("""
        CREATE TABLE IF NOT EXISTS stocks (
            ticker       VARCHAR PRIMARY KEY,
            name         VARCHAR NOT NULL,
            sector       VARCHAR,
            industry     VARCHAR,
            market_cap   BIGINT,
            exchange     VARCHAR,
            updated_at   TIMESTAMP DEFAULT current_timestamp
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_prices (
            ticker       VARCHAR NOT NULL,
            date         DATE NOT NULL,
            open         DOUBLE,
            high         DOUBLE,
            low          DOUBLE,
            close        DOUBLE,
            adj_close    DOUBLE,
            volume       BIGINT,
            PRIMARY KEY (ticker, date)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS fundamentals (
            ticker              VARCHAR PRIMARY KEY,
            pe_ratio            DOUBLE,
            pb_ratio            DOUBLE,
            ps_ratio            DOUBLE,
            eps                 DOUBLE,
            roe                 DOUBLE,
            debt_to_equity      DOUBLE,
            dividend_yield      DOUBLE,
            beta                DOUBLE,
            fifty_two_week_high DOUBLE,
            fifty_two_week_low  DOUBLE,
            avg_volume          BIGINT,
            updated_at          TIMESTAMP DEFAULT current_timestamp
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS dividends (
            ticker       VARCHAR NOT NULL,
            ex_date      DATE NOT NULL,
            payment_date DATE,
            amount       DOUBLE,
            PRIMARY KEY (ticker, ex_date)
        )
    """)

    # --- Portfolio Tables ---
    conn.execute("""
        CREATE TABLE IF NOT EXISTS portfolios (
            id           INTEGER PRIMARY KEY,
            name         VARCHAR NOT NULL,
            description  VARCHAR,
            user_id      INTEGER,
            created_at   TIMESTAMP DEFAULT current_timestamp
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id           INTEGER PRIMARY KEY,
            portfolio_id INTEGER NOT NULL,
            ticker       VARCHAR NOT NULL,
            trade_type   VARCHAR NOT NULL,
            quantity     DOUBLE NOT NULL,
            price        DOUBLE NOT NULL,
            commission   DOUBLE DEFAULT 0,
            trade_date   DATE NOT NULL,
            note         VARCHAR,
            created_at   TIMESTAMP DEFAULT current_timestamp
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS portfolio_snapshots (
            portfolio_id INTEGER NOT NULL,
            date         DATE NOT NULL,
            total_value  DOUBLE,
            total_cost   DOUBLE,
            PRIMARY KEY (portfolio_id, date)
        )
    """)

    # --- Calendar Tables ---
    conn.execute("""
        CREATE TABLE IF NOT EXISTS economic_events (
            id           INTEGER PRIMARY KEY,
            event_name   VARCHAR NOT NULL,
            country      VARCHAR DEFAULT 'US',
            event_date   DATE NOT NULL,
            event_time   VARCHAR,
            actual       DOUBLE,
            forecast     DOUBLE,
            previous     DOUBLE,
            importance   VARCHAR DEFAULT 'medium',
            unit         VARCHAR,
            cached_at    TIMESTAMP DEFAULT current_timestamp
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS earnings_calendar (
            id              INTEGER PRIMARY KEY,
            ticker          VARCHAR NOT NULL,
            company_name    VARCHAR,
            earnings_date   DATE NOT NULL,
            eps_estimate    DOUBLE,
            eps_actual      DOUBLE,
            revenue_estimate DOUBLE,
            revenue_actual  DOUBLE,
            cached_at       TIMESTAMP DEFAULT current_timestamp
        )
    """)

    _create_sequence_if_not_exists(conn, "seq_econ_event_id")
    _create_sequence_if_not_exists(conn, "seq_earnings_id")

    # --- Sentiment Tables ---
    conn.execute("""
        CREATE TABLE IF NOT EXISTS news_articles (
            id           INTEGER PRIMARY KEY,
            ticker       VARCHAR,
            headline     VARCHAR NOT NULL,
            summary      VARCHAR,
            source       VARCHAR,
            url          VARCHAR,
            published_at TIMESTAMP,
            sentiment    DOUBLE,
            sentiment_label VARCHAR,
            ai_summary   VARCHAR,
            analyzed_at  TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS fear_greed_history (
            date              DATE PRIMARY KEY,
            score             DOUBLE,
            label             VARCHAR,
            vix_score         DOUBLE,
            momentum_score    DOUBLE,
            put_call_score    DOUBLE,
            high_low_score    DOUBLE,
            volume_score      DOUBLE
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_reports (
            date         DATE PRIMARY KEY,
            content      TEXT,
            generated_at TIMESTAMP
        )
    """)

    # --- Sequences (for auto-increment IDs) ---
    _create_sequence_if_not_exists(conn, "seq_news_id")
    _create_sequence_if_not_exists(conn, "seq_trade_id")
    _create_sequence_if_not_exists(conn, "seq_portfolio_id")

    logger.info("Database initialized: all tables and sequences created.")


def _create_sequence_if_not_exists(
    conn: duckdb.DuckDBPyConnection, name: str
) -> None:
    """Create a DuckDB sequence if it doesn't already exist.

    Args:
        conn: Active DuckDB connection.
        name: Name of the sequence to create.
    """
    try:
        conn.execute(f"CREATE SEQUENCE IF NOT EXISTS {name} START 1")
    except duckdb.CatalogException:
        logger.debug("Sequence %s already exists.", name)


def close_connection() -> None:
    """Close the current thread's DuckDB connection if open."""
    conn = getattr(_local, "connection", None)
    if conn is not None:
        conn.close()
        _local.connection = None
        logger.info("DuckDB connection closed for thread %s", threading.current_thread().name)
