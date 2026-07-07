"""보유 종목 과열(이격) 리밸런싱 점검 — Telegram 알림.

예측이 아니라 '리스크 고지'다. 200일선 대비 이격이 자기 이력 상위이면서
비중/미실현수익이 큰 종목을, 매도 신호가 아닌 '변동성이 커질 수 있으니 목표
비중을 점검하라'는 알림으로 발송한다.

근거(백테스트):
  - RSI·이격 '과열' 자체는 향후 수익이 오히려 높음(모멘텀) → 매도 신호 아님
  - 단, 극단 이격 종목은 향후 낙폭·변동성이 더 큼 → 리밸런싱(리스크 관리) 정당

실행:
  python scripts/portfolio_risk_alert.py            # 정상 (플래그 있을 때만 발송)
  python scripts/portfolio_risk_alert.py --dry-run  # 발송 안 함, 콘솔 출력만
  python scripts/portfolio_risk_alert.py --force     # 플래그 없어도 요약 발송

매일 US 마감 후(예: 07:30 KST) Windows Task Scheduler로 실행.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import types
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

_APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_APP_DIR))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(_APP_DIR / "data" / "logs" / "portfolio_risk_alert.log",
                            encoding="utf-8"),
    ],
)
logger = logging.getLogger("portfolio-risk-alert")

_OWNER_EMAIL = "sksk28y@gmail.com"

# ── 플래그 임계값 ────────────────────────────────────────────────────────────
STRETCH_PCT = 85.0     # 이격이 자기 이력 상위 15% 이상이면 '과열'
MIN_WEIGHT = 0.03      # 비중 3% 미만은 리밸런싱 무의미 → 플래그 제외
WEIGHT_TH = 0.15       # 비중 15% 이상 = 집중
GAIN_TH = 50.0         # 미실현 수익 +50% 이상 = 큰 승자
HIST_DAYS = 756        # 이격 백분위 계산 기간(약 3년)
MIN_HIST = 250         # 최소 이력(200일선 + 여유)

_STATE_PATH = _APP_DIR / "data" / "cache" / "portfolio_alert_state.json"


# ── Streamlit stub (headless에서 database.py가 Turso secrets를 읽도록) ──────
def _load_secrets() -> dict:
    p = _APP_DIR / ".streamlit" / "secrets.toml"
    if not p.exists():
        return {}
    try:
        import tomllib
        return tomllib.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("secrets.toml 파싱 실패: %s", e)
        return {}


def _bootstrap_streamlit() -> None:
    _secrets = _load_secrets()

    class _Secrets(dict):
        def get(self, k, default=None):
            return super().get(k, default)

    def _passthrough(*a, **k):
        if a and callable(a[0]):
            return a[0]
        def _w(fn):
            return fn
        return _w

    st = types.ModuleType("streamlit")
    st.cache_data = _passthrough
    st.cache_resource = _passthrough
    st.secrets = _Secrets(_secrets)
    st.session_state = {}
    for _n in ("warning", "error", "info", "success", "caption", "markdown", "write"):
        setattr(st, _n, lambda *a, **k: None)
    sys.modules["streamlit"] = st


# ── Telegram ─────────────────────────────────────────────────────────────────
def _load_telegram() -> tuple[str, list[str]]:
    workspace = _APP_DIR.parent.parent  # claude/
    env = workspace / "stock_briefing" / ".env"
    if env.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(env, override=False)
        except ImportError:
            pass
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("QUANT_LAB_CHAT_ID", "").strip() or os.environ.get("TELEGRAM_CHAT_ID", "")
    chats = [c.strip() for c in chat.split(",") if c.strip()]
    return token, chats


def _send_telegram(token: str, chats: list[str], text: str) -> None:
    for cid in chats:
        payload = urllib.parse.urlencode({
            "chat_id": cid, "text": text, "parse_mode": "Markdown",
            "disable_web_page_preview": "true",
        }).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage", data=payload, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=15):
                logger.info("Telegram 발송: %s", cid)
        except Exception as e:
            logger.error("Telegram 발송 실패(%s): %s", cid, e)


# ── 포트폴리오 로드 (owner, 전 포트폴리오 티커 합산) ─────────────────────────
def _load_owner_holdings() -> list[dict]:
    from database import get_connection
    from services.portfolio_service import get_portfolios, get_holdings

    conn = get_connection()
    row = conn.execute(
        "SELECT id FROM users WHERE lower(email) = ?", (_OWNER_EMAIL.lower(),)
    ).fetchone()
    if not row:
        logger.error("owner 사용자(%s)를 찾을 수 없음", _OWNER_EMAIL)
        return []
    owner_id = row[0]

    ports = get_portfolios(user_id=owner_id)
    agg: dict[str, dict] = {}
    grand_total = 0.0
    for p in ports:
        data = get_holdings(p["id"])
        if not data:
            continue
        for h in data.get("holdings", []):
            mv = h.get("market_value")
            if not mv:
                continue
            t = h["ticker"]
            a = agg.setdefault(t, {"ticker": t, "market_value": 0.0,
                                   "total_cost": 0.0, "name": h.get("name")})
            a["market_value"] += mv
            a["total_cost"] += h.get("total_cost") or 0.0
            grand_total += mv

    for a in agg.values():
        a["weight"] = a["market_value"] / grand_total if grand_total else 0.0
        a["gain_pct"] = ((a["market_value"] - a["total_cost"]) / a["total_cost"] * 100
                         if a["total_cost"] else 0.0)
    return sorted(agg.values(), key=lambda x: x["weight"], reverse=True)


# ── 이격도 + 자기 이력 백분위 ────────────────────────────────────────────────
def _extension_metrics(ticker: str) -> dict | None:
    import numpy as np
    import yfinance as yf
    try:
        c = yf.Ticker(ticker).history(period="3y", auto_adjust=True)["Close"].dropna()
    except Exception as e:
        logger.warning("%s 가격 조회 실패: %s", ticker, e)
        return None
    if len(c) < MIN_HIST:
        return None
    sma200 = c.rolling(200).mean()
    ext = (c / sma200 - 1).dropna()
    if ext.empty:
        return None
    cur = float(ext.iloc[-1])
    hist = ext.tail(HIST_DAYS)
    pct = float((hist <= cur).mean() * 100)  # 현재 이격의 백분위
    return {"ext": cur, "ext_pct": pct}


def _classify(h: dict) -> str:
    """🔴 / 🟡 / 🟢 반환."""
    if h.get("ext_pct") is None:
        return "🟢"
    # 비중이 미미한 포지션은 과열이어도 리밸런싱 의미가 없음
    if h["weight"] < MIN_WEIGHT:
        return "🟢"
    stretched = h["ext_pct"] >= STRETCH_PCT
    if not stretched:
        return "🟢"
    concentrated_or_winner = (h["weight"] >= WEIGHT_TH) or (h["gain_pct"] >= GAIN_TH)
    return "🔴" if concentrated_or_winner else "🟡"


# ── 상태(이전 플래그) 저장/로드 ──────────────────────────────────────────────
def _load_state() -> dict:
    if _STATE_PATH.exists():
        try:
            return json.loads(_STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_state(flagged: dict[str, str]) -> None:
    _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _STATE_PATH.write_text(
        json.dumps({"updated_at": datetime.now(timezone.utc).isoformat(),
                    "flagged": flagged}, ensure_ascii=False, indent=2),
        encoding="utf-8")


# ── 메시지 ───────────────────────────────────────────────────────────────────
def _format_message(rows: list[dict], prev: dict) -> str:
    today = date.today().strftime("%m/%d")
    reds = [r for r in rows if r["flag"] == "🔴"]
    yellows = [r for r in rows if r["flag"] == "🟡"]
    greens = len(rows) - len(reds) - len(yellows)

    lines = [
        f"📊 *포트폴리오 과열 점검* ({today})",
        "",
        "_⚠️ 매도 신호가 아닙니다._ 아래 종목은 200일선 대비 과열 구간이라 "
        "*변동성·낙폭이 커질 수 있으니 목표 비중을 점검*하라는 리스크 고지입니다. "
        "(과열 자체는 오히려 추가 상승 경향이 있어, 리밸런싱은 리스크 관리 목적일 때만.)",
        "",
    ]

    def _fmt(r: dict) -> list[str]:
        new = "  🆕" if r["ticker"] not in prev else ""
        return [
            f"{r['flag']} *{r['ticker']}*{new}",
            f"   이격 {r['ext']*100:+.0f}% (자기 이력 상위 {100-r['ext_pct']:.0f}%) · "
            f"비중 {r['weight']*100:.0f}% · 수익 {r['gain_pct']:+.0f}%",
        ]

    if reds:
        lines.append("━━━ 🔴 과열 + 집중/큰수익 ━━━")
        for r in reds:
            lines += _fmt(r)
            lines.append("   → 목표 비중 초과 시 *일부 리밸런싱* 고려")
        lines.append("")
    if yellows:
        lines.append("━━━ 🟡 과열 (비중·수익은 보통) ━━━")
        for r in yellows:
            lines += _fmt(r)
        lines.append("")

    lines.append(f"🟢 나머지 {greens}개 정상")
    lines.append("")
    lines.append("_Stock Dashboard · 과열 리밸런싱 점검 (참고용, 투자권유 아님)_")
    return "\n".join(lines)


# ── Main ─────────────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="발송 안 함, 콘솔 출력만")
    ap.add_argument("--force", action="store_true", help="플래그 없어도 발송")
    args = ap.parse_args()

    (_APP_DIR / "data" / "logs").mkdir(parents=True, exist_ok=True)
    _bootstrap_streamlit()

    holdings = _load_owner_holdings()
    if not holdings:
        logger.info("보유 종목 없음 — 종료")
        return 0
    logger.info("보유 종목 %d개 분석 시작", len(holdings))

    rows = []
    for h in holdings:
        m = _extension_metrics(h["ticker"])
        if m:
            h.update(m)
        else:
            h["ext"], h["ext_pct"] = None, None
        h["flag"] = _classify(h)
        rows.append(h)
        logger.info("  %s: 이격%s 비중 %.0f%% 수익 %+.0f%% → %s",
                    h["ticker"],
                    f" {h['ext']*100:+.0f}%(상위{100-h['ext_pct']:.0f}%)" if h.get("ext_pct") is not None else " N/A",
                    h["weight"]*100, h["gain_pct"], h["flag"])

    flagged = {r["ticker"]: r["flag"] for r in rows if r["flag"] in ("🔴", "🟡")}
    prev = _load_state().get("flagged", {})

    if not flagged and not args.force:
        logger.info("플래그 종목 없음 — 발송 건너뜀")
        _save_state(flagged)
        return 0

    msg = _format_message(rows, prev)
    if args.dry_run:
        print("\n" + msg + "\n")
        logger.info("[dry-run] 발송 안 함")
        return 0

    token, chats = _load_telegram()
    if not token or not chats:
        logger.error("Telegram 설정 없음 (stock_briefing/.env)")
        return 1
    _send_telegram(token, chats, msg)
    _save_state(flagged)
    logger.info("완료: 🔴%d 🟡%d",
                sum(1 for v in flagged.values() if v == "🔴"),
                sum(1 for v in flagged.values() if v == "🟡"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
