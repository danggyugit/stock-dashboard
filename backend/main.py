"""FastAPI application entry point.

Configures the app with CORS, lifespan events, and router registration.
Run with: uvicorn main:app --host 0.0.0.0 --port 8001 --reload
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from db import init_db, close_connection
from scheduler import start_scheduler, stop_scheduler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown events.

    Startup:
    - Ensures data directory exists
    - Initializes DuckDB tables and sequences
    - Starts APScheduler

    Shutdown:
    - Stops APScheduler
    - Closes DuckDB connection
    """
    # --- Startup ---
    settings = get_settings()
    data_dir = Path(settings.DUCKDB_PATH).parent
    data_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Data directory ensured: %s", data_dir.resolve())

    init_db()
    logger.info("Database initialized.")

    scheduler = start_scheduler()
    logger.info("Scheduler started.")

    # Backfill Fear & Greed history if needed
    try:
        from services.sentiment_service import SentimentService
        from db import get_connection as _get_conn
        conn = _get_conn()
        count = conn.execute("SELECT COUNT(*) FROM fear_greed_history").fetchone()[0]
        if count < 10:
            svc = SentimentService()
            filled = svc.backfill_fear_greed(days=60)
            logger.info("F&G history backfilled: %d new points (total was %d).", filled, count)
    except Exception:
        logger.exception("F&G backfill failed (non-critical).")

    # Skip initial cache warm on free tier to avoid memory issues
    logger.info("Skipping initial cache warm (free tier).")

    yield

    # --- Shutdown ---
    stop_scheduler()
    close_connection()
    logger.info("Application shutdown complete.")


app = FastAPI(
    title="Stock Dashboard API",
    description="Backend API for Stock Dashboard — market data, portfolio tracking, and sentiment analysis.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware for frontend dev server
import os

_allowed_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
# Add production frontend URL from env
_frontend_url = os.environ.get("FRONTEND_URL")
if _frontend_url:
    _allowed_origins.append(_frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
from auth import router as auth_router
from routers.market import router as market_router
from routers.portfolio import router as portfolio_router
from routers.sentiment import router as sentiment_router

app.include_router(auth_router)
app.include_router(market_router)
app.include_router(portfolio_router)
app.include_router(sentiment_router)


@app.get("/")
def root() -> dict:
    """Health check endpoint.

    Returns:
        Application status and version.
    """
    return {
        "status": "ok",
        "app": "Stock Dashboard API",
        "version": "0.1.0",
    }


@app.get("/health")
def health() -> dict:
    """Detailed health check.

    Returns:
        Health status with database connectivity check.
    """
    from db import get_connection

    try:
        conn = get_connection()
        conn.execute("SELECT 1").fetchone()
        db_status = "connected"
    except Exception:
        db_status = "disconnected"

    return {
        "status": "ok",
        "database": db_status,
    }
