"""월간 리밸런싱 알림 — AI Quant Lab 오늘의 추천 종목을 텔레그램으로 발송.

매월 1일 11:30 KST Windows Task Scheduler 실행 (send_rebalancing_alert.bat).
캐시 파일 (data/cache/backtests/*.json) 의 today_picks 를 읽어 발송.

사전 조건:
  - run_preset_backtests.py (11:00 KST) 가 오늘 캐시를 갱신했을 것
  - stock_briefing/.env 에 TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID 설정

사용법:
  python scripts/send_rebalancing_alert.py          # 정상 실행
  python scripts/send_rebalancing_alert.py --force  # 날짜 체크 없이 강제 발송
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
from datetime import date
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("rebalancing-alert")

# Telegram credentials — stock_briefing/.env 공유 (같은 워크스페이스)
_WORKSPACE = Path(__file__).resolve().parent.parent.parent.parent  # claude/
_BRIEFING_ENV = _WORKSPACE / "stock_briefing" / ".env"
if _BRIEFING_ENV.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_BRIEFING_ENV, override=False)
        logger.info("Loaded .env from stock_briefing")
    except ImportError:
        logger.warning("python-dotenv not installed; using system env only")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_IDS = [
    c.strip()
    for c in os.environ.get("TELEGRAM_CHAT_ID", "").split(",")
    if c.strip()
]

_APP_DIR = Path(__file__).resolve().parent.parent
_CACHE_DIR = _APP_DIR / "data" / "cache" / "backtests"

PRESET_ORDER = ["it_invvol", "it_equal", "it_invvol_regime"]


# ── Helpers ────────────────────────────────────────────────────────────────

def _load_preset(preset_id: str) -> dict | None:
    p = _CACHE_DIR / f"{preset_id}.json"
    if not p.exists():
        logger.warning("캐시 없음: %s", p)
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("%s 로드 실패: %s", preset_id, e)
        return None


def _is_first_trading_day() -> bool:
    """오늘이 당월 첫 3 거래일 이내면 True (주말·공휴일 대비 여유분)."""
    today = date.today()
    if today.weekday() >= 5:
        return False
    # 1~3일 이내
    return today.day <= 3


def _format_message(presets: list[dict]) -> str:
    today_str = date.today().strftime("%Y년 %m월 %d일")
    lines = [
        f"🔄 *AI Quant Lab 월간 리밸런싱 알림*",
        f"📅 {today_str}",
        "",
    ]

    for p in presets:
        name = p.get("name", p.get("preset_id", "?"))
        picks: list[dict] = p.get("today_picks") or []
        regime = p.get("today_regime")
        cash_pct = p.get("today_cash_ratio_pct")
        picks_at = (p.get("today_picks_at") or "")[:10]
        updated_at = (p.get("updated_at") or "")[:10]

        lines.append("━━━━━━━━━━━━━━━━━━━")
        lines.append(f"🤖 *{name}*")

        status_parts = []
        if regime:
            icon = "🐂" if regime == "Bull" else "🐻" if regime == "Bear" else "😐"
            status_parts.append(f"{icon} {regime}")
        if cash_pct is not None:
            status_parts.append(f"현금 {cash_pct:.0f}%")
        if status_parts:
            lines.append("  " + " · ".join(status_parts))

        lines.append("")

        if not picks:
            lines.append("  종목 데이터 없음 (캐시 갱신 필요)")
        else:
            lines.append("```")
            lines.append(f"{'종목':<6}  {'비중':>5}  {'1M':>6}  {'3M':>6}  {'12M':>7}")
            lines.append("─" * 38)
            for pk in picks:
                ticker = str(pk.get("ticker", "?"))
                weight = pk.get("weight") or 0.0
                m1 = pk.get("Mom_1m")
                m3 = pk.get("Mom_3m")
                m12 = pk.get("Mom_12m")

                def _fmt(v: float | None) -> str:
                    return f"{v * 100:+.1f}%" if v is not None else "   —  "

                lines.append(
                    f"{ticker:<6}  {weight * 100:>4.1f}%  "
                    f"{_fmt(m1):>6}  {_fmt(m3):>6}  {_fmt(m12):>7}"
                )
            lines.append("```")

        if picks_at:
            lines.append(f"  _(기준: {picks_at} · 캐시: {updated_at})_")
        lines.append("")

    lines.append("━━━━━━━━━━━━━━━━━━━")
    lines.append("_Stock Dashboard · AI Quant Lab 월간 리밸런싱 알림_")
    return "\n".join(lines)


def _send_telegram(token: str, chat_id: str, text: str) -> None:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
    }).encode()
    req = urllib.request.Request(url, data=payload, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        if resp.status != 200:
            raise RuntimeError(f"Telegram API {resp.status}")


# ── Main ───────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="날짜 체크 없이 강제 발송")
    args = parser.parse_args()

    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN 없음. stock_briefing/.env 확인.")
        return 1
    if not TELEGRAM_CHAT_IDS:
        logger.error("TELEGRAM_CHAT_ID 없음. stock_briefing/.env 확인.")
        return 1

    if not args.force and not _is_first_trading_day():
        logger.info("오늘은 월초 첫 거래일이 아님 — 발송 건너뜀 (--force 로 강제 실행 가능)")
        return 0

    presets_data = [d for pid in PRESET_ORDER if (d := _load_preset(pid))]
    if not presets_data:
        logger.error("캐시 파일 없음. run_preset_backtests.py 먼저 실행하세요.")
        return 1

    msg = _format_message(presets_data)
    logger.info("발송 메시지 준비 완료 (%d chars)", len(msg))

    ok = 0
    for chat_id in TELEGRAM_CHAT_IDS:
        try:
            _send_telegram(TELEGRAM_BOT_TOKEN, chat_id, msg)
            logger.info("[ok] %s 발송 완료", chat_id)
            ok += 1
            time.sleep(1.5)
        except Exception as e:
            logger.error("[fail] %s 발송 실패: %s", chat_id, e)

    return 0 if ok > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
