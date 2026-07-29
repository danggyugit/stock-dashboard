"""SEC Intelligence 스케줄러 — 13F + 내부자 스캔 + Telegram 알림.

실행 주기:
  - 매일 11:30 KST: 내부자 대량 매수 스캔 + 알림
  - 분기별 (1/15, 4/15, 7/15, 10/15): 신규 13F 수집 + 알림

사용법:
  python scripts/fetch_sec_intelligence.py              # 자동 (날짜 판단)
  python scripts/fetch_sec_intelligence.py --13f        # 13F 강제 수집
  python scripts/fetch_sec_intelligence.py --insider    # 내부자 스캔만
  python scripts/fetch_sec_intelligence.py --force      # 전체 강제 실행
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
_APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_APP_DIR))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            _APP_DIR / "data" / "logs" / "fetch_sec_intelligence.log",
            encoding="utf-8",
        ),
    ],
)
logger = logging.getLogger("sec-intelligence")

# Telegram 설정 (stock_briefing/.env 공유)
_WORKSPACE = _APP_DIR.parent.parent  # claude/
_BRIEFING_ENV = _WORKSPACE / "stock_briefing" / ".env"
if _BRIEFING_ENV.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_BRIEFING_ENV, override=False)
    except ImportError:
        pass

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_IDS = [
    c.strip()
    for c in os.environ.get("TELEGRAM_CHAT_ID", "").split(",")
    if c.strip()
]

# S&P 500 상위 종목 (내부자 스캔 대상)
_SP500_TOP = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "BRK-B",
    "JPM", "UNH", "XOM", "V", "MA", "LLY", "JNJ", "PG", "HD", "MRK",
    "ABBV", "KO", "CVX", "PEP", "COST", "ADBE", "CRM", "MCD", "TMO",
    "BAC", "ACN", "LIN", "AVGO", "CSCO", "ABT", "WMT", "TXN", "NEE",
    "DHR", "NKE", "PM", "NFLX", "ORCL", "AMGN", "MS", "RTX", "IBM",
    "INTC", "QCOM", "HON", "LOW", "AMD", "SPGI", "INTU", "CAT", "GE",
    "AMAT", "DE", "SBUX", "GS", "AXP", "BLK", "SYK", "GILD", "MDLZ",
    "ADI", "VRTX", "SCHW", "NOW", "REGN", "ISRG", "PLD", "ZTS", "BSX",
    "PANW", "MMC", "ELV", "ETN", "AON", "CB", "TJX", "MU", "LRCX",
    "SLB", "FCX", "WM", "CTAS", "SO", "DUK", "CL", "EOG", "KLAC",
    "HCA", "MCK", "NSC", "ITW", "FI", "USB", "EMR", "APD", "PNC",
    "AIG", "COF", "TGT", "PYPL", "UBER", "DDOG", "SNOW", "PLTR",
]

_MIN_INSIDER_BUY_USD = 100_000  # $100K 이상 매수만 알림


# ── Telegram ──────────────────────────────────────────────────────────────────

def _send_telegram(text: str) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_IDS:
        logger.warning("Telegram 설정 없음 — 발송 건너뜀")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    for chat_id in TELEGRAM_CHAT_IDS:
        payload = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
        }).encode()
        req = urllib.request.Request(url, data=payload, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status != 200:
                    logger.error("Telegram 발송 실패 (%s): %s", chat_id, resp.status)
                else:
                    logger.info("Telegram 발송 완료: %s", chat_id)
        except Exception as e:
            logger.error("Telegram 발송 오류 (%s): %s", chat_id, e)
        time.sleep(1.0)


# ── 13F 수집 ──────────────────────────────────────────────────────────────────

def _is_13f_season() -> bool:
    """13F 공시 시즌 여부 (분기 종료 후 ~45일: 1~2월, 4~5월, 7~8월, 10~11월)."""
    today = date.today()
    return today.month in (1, 2, 4, 5, 7, 8, 10, 11)


def _format_13f_alert(manager_data: dict, diff: dict) -> str:
    """13F 변화 텔레그램 메시지 포맷."""
    name = manager_data.get("manager", manager_data.get("name", "?"))
    period = manager_data.get("period", "")
    filed = manager_data.get("filed_date", "")
    total_holdings = len(manager_data.get("holdings", []))

    lines = [
        f"🐳 *{name} — 신규 13F 공시*",
        f"📅 기준일: {period} · 공시일: {filed}",
        f"📊 총 {total_holdings}개 종목 보유",
        "",
    ]

    # 신규 포지션
    new_pos = diff.get("new", [])[:5]
    if new_pos:
        lines.append("🆕 *신규 매수*")
        for h in new_pos:
            ticker = h.get("ticker") or h.get("company", "?")
            val = h.get("value_k", 0)
            pct = h.get("pct_port", 0)
            lines.append(f"  • {ticker} — ${val/1000:.1f}M ({pct:.1f}%)")
        lines.append("")

    # 크게 늘린 포지션
    added = sorted(diff.get("added", []), key=lambda x: abs(x.get("pct_change", 0)), reverse=True)[:5]
    if added:
        lines.append("📈 *비중 확대*")
        for h in added:
            ticker = h.get("ticker") or h.get("company", "?")
            pct_chg = h.get("pct_change", 0)
            val = h.get("value_k", 0)
            lines.append(f"  • {ticker} +{pct_chg:.0f}% — ${val/1000:.1f}M")
        lines.append("")

    # 청산
    sold = diff.get("sold", [])[:5]
    if sold:
        lines.append("🔴 *청산*")
        for h in sold:
            ticker = h.get("ticker") or h.get("company", "?")
            val = h.get("value_k", 0)
            lines.append(f"  • {ticker} — ${val/1000:.1f}M (전분기)")
        lines.append("")

    lines.append("_Stock Dashboard · SEC Intelligence_")
    return "\n".join(lines)


def run_13f_fetch(force: bool = False) -> int:
    """모든 고래 매니저의 최신 13F를 수집하고, 변화가 있으면 알림 발송."""
    from services.sec_intelligence_service import (
        WHALE_MANAGERS,
        fetch_and_cache_holdings,
        load_cached_holdings,
        load_prev_cached_holdings,
        compute_holdings_diff,
        _load_metadata,
    )

    logger.info("13F 수집 시작 (%d 매니저)", len(WHALE_MANAGERS))
    alerted = 0

    for m in WHALE_MANAGERS:
        cik = m["cik"]
        logger.info("처리 중: %s (%s)", m["manager"], cik)
        try:
            prev = load_cached_holdings(cik)
            curr = fetch_and_cache_holdings(cik, force=force)

            if not curr:
                logger.warning("  -> 수집 실패 또는 데이터 없음")
                continue

            logger.info("  -> %s 기준 %d종목 수집 완료", curr["period"], len(curr.get("holdings", [])))

            # 이전 데이터와 비교해 변화가 있으면 알림
            if prev and prev.get("period") != curr.get("period"):
                diff = compute_holdings_diff(curr, prev)
                total_changes = sum(len(diff[k]) for k in ("new", "added", "reduced", "sold"))
                if total_changes > 0:
                    msg = _format_13f_alert(curr, diff)
                    _send_telegram(msg)
                    alerted += 1
                    logger.info("  -> 알림 발송 완료 (변화 %d건)", total_changes)

        except Exception as e:
            logger.error("  -> 오류: %s", e)

        time.sleep(1.5)  # EDGAR rate limit 준수

    logger.info("13F 수집 완료. 알림 발송: %d건", alerted)
    return alerted


# ── 내부자 스캔 ───────────────────────────────────────────────────────────────

def _format_insider_alert(rows: list[dict]) -> str:
    today_str = date.today().strftime("%Y년 %m월 %d일")
    lines = [
        f"👤 *내부자 대량 매수 알림*",
        f"📅 {today_str} (최근 7일)",
        f"💰 기준: ${_MIN_INSIDER_BUY_USD:,} 이상 매수",
        "",
        "```",
        f"{'종목':<6}  {'내부자':<18}  {'직책':<12}  {'금액':>10}",
        "─" * 55,
    ]

    for row in rows[:15]:
        ticker = str(row.get("Ticker", "?"))[:6]
        insider = str(row.get("Insider", "?"))[:18]
        role = str(row.get("Role", ""))[:12]
        val = row.get("Value ($)", 0) or 0
        val_str = f"${val:,.0f}"[:10]
        lines.append(f"{ticker:<6}  {insider:<18}  {role:<12}  {val_str:>10}")

    lines.append("```")
    lines.append("")
    lines.append("_Stock Dashboard · SEC Intelligence_")
    return "\n".join(lines)


def run_insider_scan(days: int = 7) -> int:
    """S&P 500 상위 종목 내부자 대량 매수 스캔 + 알림."""
    from services.sec_intelligence_service import (
        scan_large_insider_buys,
        save_insider_scan,
    )

    logger.info("내부자 스캔 시작 (%d종목, 최근 %d일)", len(_SP500_TOP), days)

    try:
        df = scan_large_insider_buys(_SP500_TOP, days=days, min_value_usd=_MIN_INSIDER_BUY_USD)
    except Exception as e:
        logger.error("내부자 스캔 실패: %s", e)
        return 0

    if df.empty:
        logger.info("대량 매수 없음")
        save_insider_scan([])
        return 0

    rows = df.to_dict(orient="records")
    # fetched_at 추가
    for r in rows:
        r["fetched_at"] = datetime.now(timezone.utc).isoformat()
        # JSON serializable 변환
        for k, v in r.items():
            if hasattr(v, "item"):  # numpy scalar
                r[k] = v.item()
            elif v != v:  # NaN
                r[k] = None

    save_insider_scan(rows)
    logger.info("내부자 스캔 완료: %d건", len(rows))

    if rows:
        msg = _format_insider_alert(rows)
        _send_telegram(msg)
        logger.info("내부자 알림 발송 완료")

    return len(rows)


# ── Git push ──────────────────────────────────────────────────────────────────

def _git_push() -> None:
    import subprocess as sp

    repo = _APP_DIR.parent  # stock_dashboard/ (git repo root)
    cache_sec = _APP_DIR / "data" / "cache" / "sec"
    files = list(cache_sec.rglob("*.json"))
    rel_files = [str(f.relative_to(repo)) for f in files]

    if not rel_files:
        logger.info("Git push 대상 없음")
        return

    kst_now = datetime.now(timezone.utc).strftime("%Y/%m/%d %H:%M")
    try:
        sp.run(["git", "add"] + rel_files, cwd=repo, check=True)
        sp.run(
            ["git", "commit", "-m", f"chore: refresh SEC intelligence cache [skip ci] ({kst_now} KST)"],
            cwd=repo, check=True,
        )
        sp.run(["git", "push", "origin", "main"], cwd=repo, check=True)
        logger.info("Git push 완료")
    except sp.CalledProcessError as e:
        logger.warning("Git push 실패 (비치명적): %s", e)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--13f", dest="do_13f", action="store_true", help="13F 강제 수집")
    parser.add_argument("--insider", dest="do_insider", action="store_true", help="내부자 스캔만")
    parser.add_argument("--force", action="store_true", help="캐시 무시 전체 실행")
    args = parser.parse_args()

    # 로그 디렉토리 생성
    (_APP_DIR / "data" / "logs").mkdir(parents=True, exist_ok=True)

    did_work = False

    # 13F 수집
    do_13f = args.do_13f or args.force or _is_13f_season()
    if do_13f or not args.do_insider:
        if do_13f:
            run_13f_fetch(force=args.force)
            did_work = True

    # 내부자 스캔 (매일)
    run_insider_scan(days=7)
    did_work = True

    if did_work:
        _git_push()

    return 0


if __name__ == "__main__":
    sys.exit(main())
