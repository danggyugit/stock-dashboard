"""Site-wide i18n (English + Korean).

Single source of truth for the EN / KO toggle. Default = English.

Usage from any page:

    from services.i18n import t, render_lang_toggle

    render_lang_toggle()         # render the EN | KO toggle (sidebar)
    st.markdown(t("page.dashboard.title"))

The toggle stores the current language under
`st.session_state["lang"]` so every page picks up the same setting.

Per-page legacy dictionaries (e.g. AI Quant Lab) can register
extra entries via `register_strings(...)`.
"""

from __future__ import annotations

import streamlit as st


# ─────────────────────────────────────────────────────────────
# Language state
# ─────────────────────────────────────────────────────────────

LANG_KEY = "lang"
DEFAULT_LANG = "en"
SUPPORTED_LANGS = ("en", "ko")


def get_lang() -> str:
    return st.session_state.get(LANG_KEY, DEFAULT_LANG)


def set_lang(lang: str) -> None:
    if lang in SUPPORTED_LANGS:
        st.session_state[LANG_KEY] = lang


def render_lang_toggle(location: str = "sidebar") -> None:
    """Render a compact EN / KO segmented control.

    Args:
        location: "sidebar" (default) puts the toggle at the top of the
                  sidebar so it's reachable from every page.
                  "inline" renders inline at the current cursor position.
    """
    if LANG_KEY not in st.session_state:
        st.session_state[LANG_KEY] = DEFAULT_LANG

    container = st.sidebar if location == "sidebar" else st

    # Compact pill-style toggle
    container.markdown(
        """
        <style>
        div.st-key-global_lang_toggle {
            display: flex !important;
            justify-content: flex-end !important;
            margin: 0 0 6px 0 !important;
        }
        div.st-key-global_lang_toggle [data-testid="stSegmentedControl"] button {
            font-size: 11px !important;
            padding: 3px 12px !important;
            min-height: 0 !important;
            min-width: 36px !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with container.container(key="global_lang_toggle"):
        choice = st.segmented_control(
            "lang",
            options=["EN", "KO"],
            default="EN" if get_lang() == "en" else "KO",
            label_visibility="collapsed",
            key="global_lang_seg",
        )
        new_lang = "en" if choice == "EN" else "ko"
        if new_lang != get_lang():
            set_lang(new_lang)
            st.rerun()


# ─────────────────────────────────────────────────────────────
# Translation tables
# ─────────────────────────────────────────────────────────────

# Site-wide entries (page headers, common labels, common messages).
STRINGS: dict[str, dict[str, str]] = {
    # Page headers — title + subtitle pairs
    "page.dashboard.title":      {"en": "Dashboard",
                                  "ko": "대시보드"},
    "page.dashboard.subtitle":   {"en": "Real-time market overview and portfolio summary",
                                  "ko": "실시간 시장 개요 및 포트폴리오 요약"},

    "page.heatmap.title":        {"en": "S&P 500 Market Heatmap",
                                  "ko": "S&P 500 마켓 히트맵"},
    "page.heatmap.subtitle":     {"en": "Sector-grouped treemap with live price changes",
                                  "ko": "섹터별 트리맵 + 실시간 가격 변동"},

    "page.stock_detail.title":   {"en": "Stock Detail",
                                  "ko": "종목 상세"},
    "page.stock_detail.subtitle":{"en": "Individual stock analysis with interactive chart",
                                  "ko": "개별 종목 분석 + 인터랙티브 차트"},

    "page.portfolio.title":      {"en": "Portfolio",
                                  "ko": "포트폴리오"},
    "page.portfolio.subtitle":   {"en": "Track holdings, performance, dividends, and taxes",
                                  "ko": "보유 종목 · 성과 · 배당 · 세금 추적"},

    "page.sentiment.title":      {"en": "Market Sentiment",
                                  "ko": "시장 센티먼트"},
    "page.sentiment.subtitle":   {"en": "Fear & Greed index, news sentiment, AI analysis",
                                  "ko": "Fear & Greed 지수 · 뉴스 센티먼트 · AI 분석"},

    "page.calendar.title":       {"en": "Economic & Earnings Calendar",
                                  "ko": "경제 · 실적 캘린더"},
    "page.calendar.subtitle":    {"en": "Upcoming economic events and earnings reports",
                                  "ko": "경제 지표 발표 일정 및 실적 발표"},

    "page.screener.title":       {"en": "Stock Screener",
                                  "ko": "종목 스크리너"},
    "page.screener.subtitle":    {"en": "Filter S&P 500 stocks by fundamentals",
                                  "ko": "S&P 500 종목을 펀더멘털로 필터링"},

    "page.compare.title":        {"en": "Stock Comparison",
                                  "ko": "종목 비교"},
    "page.compare.subtitle":     {"en": "Compare 2-5 stocks side by side",
                                  "ko": "2~5개 종목 나란히 비교"},

    "page.watchlist.title":      {"en": "Watchlist & Alerts",
                                  "ko": "관심 종목 & 알림"},
    "page.watchlist.subtitle":   {"en": "Track stocks and get notified on price moves",
                                  "ko": "관심 종목 추적 + 가격 변동 알림"},
}


def register_strings(extra: dict[str, dict[str, str]]) -> None:
    """Merge a per-page dict into the global table.

    Used by AI Quant Lab to register its 100+ existing keys without
    duplicating them in this file.
    """
    STRINGS.update(extra)


def t(key: str, **kwargs) -> str:
    """Translate a key. Falls back to the key itself if not found."""
    entry = STRINGS.get(key)
    if not entry:
        return key
    text = entry.get(get_lang()) or entry.get("en") or key
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):
            return text
    return text
