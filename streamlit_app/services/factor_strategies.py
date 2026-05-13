"""Factor strategy definitions for the Factor Lab.

Each strategy is a pure-Python ranking function that, given a universe
snapshot (price history + fundamentals), returns tickers sorted
best-to-worst according to the strategy's logic.

Two kinds of strategies:
  - "price"        : computed from monthly close prices only, so they are
                     100% point-in-time correct for any backtest horizon
  - "fundamentals" : depend on current fundamentals.json snapshot, so the
                     scoring is stable over time — backtests show how a
                     *today-style* portfolio would have performed. Flag
                     `has_lookahead=True` so the UI can warn users.

Adding a new strategy:
  1. Write a rank_fn(df) that returns a Series of scores (higher is better)
  2. Register it in STRATEGIES with metadata
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd


@dataclass
class Strategy:
    key: str
    name: str
    short_description: str
    long_description: str
    category: str  # "price" | "fundamentals" | "hybrid"
    has_lookahead: bool
    rank_fn: Callable[[pd.DataFrame], pd.Series]
    requires: list[str]  # columns that must exist in df


# ── Price-based scoring helpers ────────────────────────────────────────
# The DataFrame passed to rank_fn has one row per candidate ticker with
# columns computed at the rebalance date (no future info).


def _score_momentum_12m(df: pd.DataFrame) -> pd.Series:
    return df["ret_12m"]


def _score_momentum_3_12m(df: pd.DataFrame) -> pd.Series:
    # Jegadeesh-Titman style: 12-month return excluding the most recent month
    return df["ret_12m"] - df["ret_1m"]


def _score_low_volatility(df: pd.DataFrame) -> pd.Series:
    # Lower volatility → higher score
    return -df["vol_90d"]


def _score_mean_reversion_1m(df: pd.DataFrame) -> pd.Series:
    # Worst 1-month losers → higher score (contrarian short-term)
    return -df["ret_1m"]


# ── Fundamentals-based scoring helpers ─────────────────────────────────
# PIT 연간 재무제표(90일 리포팅 래그)를 사용하므로 리밸런싱 기준일의
# 실제 공개 데이터만 반영됩니다. 단, yfinance 연간 데이터 특성상
# 최근 약 4년 이전 구간은 일부 종목 데이터 누락이 발생할 수 있음.


def _score_low_per(df: pd.DataFrame) -> pd.Series:
    pe = df["pe_ratio"].where(df["pe_ratio"] > 0)
    return -pe


def _score_high_roe(df: pd.DataFrame) -> pd.Series:
    return df["roe"]


def _score_magic_formula(df: pd.DataFrame) -> pd.Series:
    pe = df["pe_ratio"].where(df["pe_ratio"] > 0)
    return (-pe).rank(pct=True) + df["roe"].rank(pct=True)


def _score_low_pbr_high_div(df: pd.DataFrame) -> pd.Series:
    pb = df["pb_ratio"].where(df["pb_ratio"] > 0)
    div = df["dividend_yield"].fillna(0)
    return (-pb).rank(pct=True) + div.rank(pct=True)


def _score_quality_low_debt(df: pd.DataFrame) -> pd.Series:
    # High ROE + Low debt-to-equity
    de = df["debt_to_equity"].fillna(df["debt_to_equity"].median())
    return df["roe"].rank(pct=True) + (-de).rank(pct=True)


def _score_high_dividend_safe(df: pd.DataFrame) -> pd.Series:
    div = df["dividend_yield"].fillna(0)
    de = df["debt_to_equity"].fillna(df["debt_to_equity"].median())
    return div.rank(pct=True) + (-de).rank(pct=True)


def _score_deep_value(df: pd.DataFrame) -> pd.Series:
    # Low PBR + Low PSR
    pb = df["pb_ratio"].where(df["pb_ratio"] > 0)
    ps = df["ps_ratio"].where(df["ps_ratio"] > 0)
    return (-pb).rank(pct=True) + (-ps).rank(pct=True)


# ── Registry ───────────────────────────────────────────────────────────

STRATEGIES: dict[str, Strategy] = {
    # === Price-based (true PIT) ========================================
    "momentum_12m": Strategy(
        key="momentum_12m",
        name="12개월 모멘텀",
        short_description="지난 12개월 수익률 상위 종목",
        long_description=(
            "최근 12개월 동안 가장 많이 오른 종목을 보유하는 전략입니다. "
            "단기 평균회귀(t-1월)를 포함한 원시 12개월 수익률 기준. "
            "최근 1개월을 제외하는 Jegadeesh-Titman 방식은 '3-12개월 모멘텀' 전략을 사용하세요."
        ),
        category="price",
        has_lookahead=False,
        rank_fn=_score_momentum_12m,
        requires=["ret_12m"],
    ),
    "momentum_3_12m": Strategy(
        key="momentum_3_12m",
        name="3-12개월 모멘텀",
        short_description="12개월 수익률 – 최근 1개월 (단기 반전 제거)",
        long_description=(
            "12개월 모멘텀의 표준 변형. 최근 1개월은 단기 평균회귀가 섞이기 때문에 "
            "'1개월 전까지의 12개월 수익률'을 본다는 개념입니다. 학계에서 'standard "
            "momentum'으로 불리는 포뮬러."
        ),
        category="price",
        has_lookahead=False,
        rank_fn=_score_momentum_3_12m,
        requires=["ret_12m", "ret_1m"],
    ),
    "low_volatility": Strategy(
        key="low_volatility",
        name="로우볼",
        short_description="변동성 낮은 종목 보유",
        long_description=(
            "최근 90일 일간수익률 표준편차가 낮은 종목을 보유하는 전략. "
            "리스크 프리미엄 퍼즐을 뒤집는 대표 아노말리 — 고변동성 종목은 "
            "장기적으로 저변동성 종목에 뒤처진다는 실증 연구."
        ),
        category="price",
        has_lookahead=False,
        rank_fn=_score_low_volatility,
        requires=["vol_90d"],
    ),
    "mean_reversion_1m": Strategy(
        key="mean_reversion_1m",
        name="단기 평균회귀",
        short_description="최근 1개월 하락 폭이 큰 종목 매수 (역발상)",
        long_description=(
            "단기간 급락한 종목이 이후 반등한다는 평균회귀 효과. "
            "모멘텀 전략과 정반대 — 최근 1개월 수익률 최하위 종목을 매수. "
            "변동성이 높고 회전율이 많아 거래비용에 민감."
        ),
        category="price",
        has_lookahead=False,
        rank_fn=_score_mean_reversion_1m,
        requires=["ret_1m"],
    ),

    # === Fundamentals-based (current snapshot — has look-ahead caveat) ==
    "low_per": Strategy(
        key="low_per",
        name="저PER",
        short_description="PER 하위 종목 (저평가 대형주)",
        long_description=(
            "Benjamin Graham의 고전적 가치투자: 이익 대비 주가가 싼 종목. "
            "Fama-French HML 팩터의 핵심 아이디어."
        ),
        category="fundamentals",
        has_lookahead=False,
        rank_fn=_score_low_per,
        requires=["pe_ratio"],
    ),
    "high_roe": Strategy(
        key="high_roe",
        name="고ROE",
        short_description="자기자본이익률 상위 종목 (퀄리티)",
        long_description=(
            "수익성이 높은 기업을 우선 보유하는 퀄리티 팩터. "
            "AQR의 'Quality Minus Junk' 논문이 대표적."
        ),
        category="fundamentals",
        has_lookahead=False,
        rank_fn=_score_high_roe,
        requires=["roe"],
    ),
    "magic_formula": Strategy(
        key="magic_formula",
        name="Magic Formula (변형)",
        short_description="저PER × 고ROE — Greenblatt 아이디어 변형",
        long_description=(
            "Joel Greenblatt 'Little Book That Beats the Market' 아이디어 기반 변형 구현. "
            "원서는 EBIT/EV + ROIC 조합이나, yfinance 데이터 신뢰성을 위해 P/E + ROE로 대체. "
            "신호 방향은 동일하나 레버리지 높은 종목에서 원서와 차이 발생 가능."
        ),
        category="fundamentals",
        has_lookahead=False,
        rank_fn=_score_magic_formula,
        requires=["pe_ratio", "roe"],
    ),
    "deep_value": Strategy(
        key="deep_value",
        name="딥밸류",
        short_description="저PBR × 저PSR (심리적 저평가주)",
        long_description=(
            "순자산 대비, 매출 대비 가장 싼 종목을 찾는 심층 가치 전략. "
            "시장이 외면한 종목에서 역발상 수익을 노림."
        ),
        category="fundamentals",
        has_lookahead=False,
        rank_fn=_score_deep_value,
        requires=["pb_ratio", "ps_ratio"],
    ),
    "quality_low_debt": Strategy(
        key="quality_low_debt",
        name="퀄리티 + 저부채",
        short_description="고ROE + 낮은 부채비율",
        long_description=(
            "재무건전성을 중시하는 보수적 퀄리티 전략. "
            "불황기에 상대적으로 덜 빠지는 경향 — 방어적 투자자 선호."
        ),
        category="fundamentals",
        has_lookahead=False,
        rank_fn=_score_quality_low_debt,
        requires=["roe", "debt_to_equity"],
    ),
    "high_div_safe": Strategy(
        key="high_div_safe",
        name="안전 고배당",
        short_description="고배당 + 저부채 (배당 지속 가능성)",
        long_description=(
            "배당수익률 상위 + 부채비율 하위. "
            "단순 고배당은 '배당 함정'(이익 감소로 배당이 곧 삭감됨) 위험이 있어 "
            "부채 필터로 지속 가능성을 확인."
        ),
        category="fundamentals",
        has_lookahead=False,
        rank_fn=_score_high_dividend_safe,
        requires=["dividend_yield", "debt_to_equity"],
    ),
    "low_pbr_high_div": Strategy(
        key="low_pbr_high_div",
        name="저PBR 고배당",
        short_description="순자산 대비 싸고 배당 주는 종목",
        long_description=(
            "전통적 가치주 + 인컴 팩터 결합. 금융·유틸리티·소비재에 편중되는 경향. "
            "성장주 강세장에서는 소외되지만 가치장에서 아웃퍼폼."
        ),
        category="fundamentals",
        has_lookahead=False,
        rank_fn=_score_low_pbr_high_div,
        requires=["pb_ratio", "dividend_yield"],
    ),
}


def list_strategies() -> list[Strategy]:
    return list(STRATEGIES.values())


def get_strategy(key: str) -> Strategy:
    if key not in STRATEGIES:
        raise KeyError(f"Unknown strategy: {key}")
    return STRATEGIES[key]
