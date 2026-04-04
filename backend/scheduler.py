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


def _warm_all_caches() -> None:
    """Job: Pre-warm all data caches so user requests are instant."""
    import time
    from services.market_service import MarketService
    from services.portfolio_service import PortfolioService
    from services.sentiment_service import SentimentService
    from providers.data_provider import MarketDataProvider
    from db import get_connection

    start = time.time()
    provider = MarketDataProvider()

    # 1. Index chart data (DOW, NASDAQ, S&P500, VIX) — intraday
    for ticker in ["^DJI", "^IXIC", "^GSPC", "^VIX"]:
        try:
            provider.get_daily_prices(ticker, period="1d", interval="5m")
        except Exception:
            logger.warning("Cache warm failed for %s chart.", ticker)

    # 2. Index info (get_indices uses individual Ticker.info)
    try:
        provider.get_indices()
    except Exception:
        logger.warning("Cache warm failed for indices.")

    # 3. Heatmap data (503 tickers batch download)
    try:
        market_svc = MarketService()
        market_svc.get_heatmap_data(period="1d")
    except Exception:
        logger.warning("Cache warm failed for heatmap.")

    # 4. Portfolio holdings + performance for all portfolios
    try:
        conn = get_connection()
        portfolio_ids = [r[0] for r in conn.execute("SELECT id FROM portfolios").fetchall()]
        port_svc = PortfolioService()
        for pid in portfolio_ids:
            try:
                port_svc.get_holdings(pid)
                for period in ["1m", "3m"]:
                    port_svc.get_performance(pid, period=period)
            except Exception:
                logger.warning("Cache warm failed for portfolio %d.", pid)
    except Exception:
        logger.warning("Cache warm failed for portfolios.")

    # 5. Fear & Greed
    try:
        SentimentService().get_fear_greed()
    except Exception:
        logger.warning("Cache warm failed for Fear & Greed.")

    elapsed = time.time() - start
    logger.info("Cache warm completed in %.1fs.", elapsed)


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

    # Cache warm: every 5 minutes (keeps all dashboard data fresh)
    _scheduler.add_job(
        _warm_all_caches,
        trigger=IntervalTrigger(minutes=5),
        id="warm_caches",
        name="Warm all data caches (5min interval)",
        replace_existing=True,
    )

    # Market data refresh (stock list + market caps) every 15 min during trading hours
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
