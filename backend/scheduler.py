"""APScheduler configuration for periodic data refresh.

Schedules market data updates during trading hours and
daily portfolio snapshot captures after market close.
"""

import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def _refresh_market_data() -> None:
    """Job: Refresh market data from providers."""
    from services.market_service import MarketService

    try:
        service = MarketService()
        result = service.refresh_market_data()
        logger.info("Scheduled market refresh: %s", result.get("message"))
    except Exception:
        logger.exception("Scheduled market refresh failed.")


def _capture_portfolio_snapshots() -> None:
    """Job: Capture daily portfolio snapshots after market close."""
    from db import get_connection
    from services.portfolio_service import PortfolioService

    try:
        conn = get_connection()
        service = PortfolioService()

        portfolios = conn.execute("SELECT id FROM portfolios").fetchall()
        today = datetime.now().date()

        for (portfolio_id,) in portfolios:
            try:
                holdings = service.get_holdings(portfolio_id)
                if holdings:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO portfolio_snapshots
                        (portfolio_id, date, total_value, total_cost)
                        VALUES (?, ?, ?, ?)
                        """,
                        [
                            portfolio_id,
                            today,
                            holdings.get("total_value", 0),
                            holdings.get("total_cost", 0),
                        ],
                    )
            except Exception:
                logger.warning("Failed to snapshot portfolio %d.", portfolio_id)

        logger.info("Captured portfolio snapshots for %d portfolios.", len(portfolios))
    except Exception:
        logger.exception("Scheduled portfolio snapshot failed.")


def start_scheduler() -> BackgroundScheduler:
    """Start the background scheduler with configured jobs.

    Jobs:
    - Market data refresh: every 15 minutes during US market hours
      (Mon-Fri, 9:30 AM - 4:00 PM ET, approximated as 14:30-21:00 UTC)
    - Portfolio snapshot: daily at 9:30 PM UTC (after market close)

    Returns:
        Started BackgroundScheduler instance.
    """
    global _scheduler  # noqa: PLW0603

    if _scheduler is not None:
        logger.warning("Scheduler already running.")
        return _scheduler

    _scheduler = BackgroundScheduler()

    # Market data refresh every 15 minutes during trading hours
    # US market: Mon-Fri, ~14:30-21:00 UTC
    _scheduler.add_job(
        _refresh_market_data,
        trigger=CronTrigger(
            day_of_week="mon-fri",
            hour="14-20",
            minute="*/15",
        ),
        id="refresh_market_data",
        name="Refresh market data (15min interval, market hours)",
        replace_existing=True,
    )

    # Portfolio snapshot after market close (21:30 UTC = 4:30 PM ET)
    _scheduler.add_job(
        _capture_portfolio_snapshots,
        trigger=CronTrigger(
            day_of_week="mon-fri",
            hour=21,
            minute=30,
        ),
        id="portfolio_snapshots",
        name="Capture daily portfolio snapshots",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info("Scheduler started with %d jobs.", len(_scheduler.get_jobs()))

    return _scheduler


def stop_scheduler() -> None:
    """Stop the background scheduler if running."""
    global _scheduler  # noqa: PLW0603
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Scheduler stopped.")
