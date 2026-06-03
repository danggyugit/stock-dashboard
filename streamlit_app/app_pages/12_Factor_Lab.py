"""Factor Lab — rule-based quant strategy backtester.

Complements the ML-driven AI Quant Lab with transparent, explainable
factor strategies (Value / Quality / Momentum / Low-Vol …). Designed so
that every pick rule can be stated in one sentence.

Three tabs:
  - Single Strategy   : pick a strategy, configure, backtest
  - Compare Strategies: run multiple strategies side-by-side
  - Strategy Guide    : browse all strategies with descriptions
"""

from __future__ import annotations

from datetime import date, timedelta

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from services.auth_service import require_auth
from components.ui import inject_css

from services.factor_strategies import list_strategies, get_strategy
from services.factor_backtest_service import (
    BacktestConfig, run_backtest, run_multiple,
)
from services.cache_loader import get_cached_stocks

_user = require_auth()
inject_css()

# ── Page styling (matches AI Quant Lab hero) ─────────────────────────
st.markdown("""
<style>
    .factor-hero {
        background: radial-gradient(ellipse at top left,
                    rgba(59,130,246,0.15) 0%,
                    rgba(15,23,42,0) 60%),
                    radial-gradient(ellipse at bottom right,
                    rgba(34,197,94,0.10) 0%,
                    rgba(15,23,42,0) 60%);
        border: 1px solid rgba(59,130,246,0.18);
        border-radius: 16px;
        padding: 28px 30px;
        margin-bottom: 20px;
    }
    .factor-hero h1 {
        font-size: 2.2rem; font-weight: 800; margin: 0 0 6px 0;
        background: linear-gradient(135deg, #60A5FA 0%, #22C55E 70%, #EAB308 100%);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        line-height: 1.15;
    }
    .factor-hero .sub { font-size: 0.95rem; color: #CBD5E1; margin: 0; }
    .factor-hero .meta {
        display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px;
    }
    .factor-hero .meta span {
        font-size: 0.72rem; font-weight: 600; color: #93C5FD;
        background: rgba(59,130,246,0.12);
        border: 1px solid rgba(59,130,246,0.3);
        padding: 4px 10px; border-radius: 999px;
    }
    .metric-card {
        background: linear-gradient(135deg, rgba(30,41,59,0.6), rgba(15,23,42,0.4));
        border: 1px solid rgba(71,85,105,0.3);
        border-radius: 12px; padding: 14px 18px;
    }
    .strategy-info {
        background: rgba(30,41,59,0.4);
        border-left: 3px solid #60A5FA;
        padding: 12px 16px;
        border-radius: 4px 12px 12px 4px;
        margin: 8px 0;
    }
    .strategy-info.look { border-left-color: #60A5FA; }
    .strategy-info.price { border-left-color: #22C55E; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="factor-hero">
  <h1>🧪 Factor Lab</h1>
  <p class="sub">룰 기반 퀀트 전략 백테스터 — 저PER, 고ROE, 모멘텀, 로우볼…</p>
  <div class="meta">
    <span>S&P 500 유니버스</span>
    <span>생존편향 보정</span>
    <span>PIT 펀더멘털</span>
    <span>벤치마크: SPY</span>
  </div>
</div>
""", unsafe_allow_html=True)

STRATEGIES = list_strategies()
KEYS = [s.key for s in STRATEGIES]
LABEL_BY_KEY = {s.key: s.name for s in STRATEGIES}
STRAT_BY_KEY = {s.key: s for s in STRATEGIES}
_CATEGORY_KO = {"price": "가격", "fundamentals": "펀더멘털", "hybrid": "하이브리드"}

# Unique sectors from stocks.json for filter dropdown
_stocks = get_cached_stocks() or []
_sectors = sorted({s.get("sector") for s in _stocks if s.get("sector")})
_cap_tiers = sorted({s.get("cap_tier") for s in _stocks if s.get("cap_tier")})

tab_single, tab_compare, tab_guide = st.tabs([
    "🎯 단일 전략", "🔀 전략 비교", "📖 전략 설명"
])


# ═══════════════════════════════════════════════════════════
# TAB 1: Single Strategy
# ═══════════════════════════════════════════════════════════
with tab_single:
    st.subheader("백테스트 설정")

    _today = date.today()
    _default_start = date(2023, 1, 1)

    with st.form("single_form", clear_on_submit=False):
        col_a, col_b = st.columns([3, 2])
        with col_a:
            strat_key = st.selectbox(
                "전략",
                options=KEYS,
                format_func=lambda k: f"{LABEL_BY_KEY[k]}  ({get_strategy(k).short_description})",
                key="single_strat",
            )
        with col_b:
            st.markdown("&nbsp;")
            _s = get_strategy(strat_key)
            if _s.category == "price":
                st.caption("🟢 가격 기반 · 장기 백테스트 가능")
            else:
                st.caption("🔵 펀더멘털 PIT · 최대 4년 권장 (yfinance 연간 데이터 한도)")

        c1, c2 = st.columns([2, 1])
        with c1:
            date_range = st.date_input(
                "백테스트 기간",
                value=(_default_start, _today),
                min_value=_today - timedelta(days=15 * 365),
                max_value=_today,
                key="single_daterange",
                help="시작일 ~ 종료일 선택 (기본 최근 5년)",
            )
        with c2:
            rebal = st.selectbox(
                "리밸런싱",
                options=[1, 3, 6, 12],
                format_func=lambda n: {1: "월별", 3: "분기", 6: "반기", 12: "연간"}[n],
                index=0, key="single_rebal",
            )

        c3, c4, c5, c6 = st.columns(4)
        with c3:
            n_stocks = st.number_input(
                "보유 종목 수", min_value=3, max_value=100, value=5, step=1,
                key="single_n",
            )
        with c4:
            tc_pct = st.number_input(
                "거래비용 (%)", min_value=0.0, max_value=2.0, value=0.3, step=0.05,
                format="%.2f", key="single_tc",
            )
        with c5:
            _single_sector_options = ["전체"] + _sectors
            _single_sector_default = (
                _single_sector_options.index("Information Technology")
                if "Information Technology" in _single_sector_options else 0
            )
            sector = st.selectbox(
                "섹터 필터", _single_sector_options,
                index=_single_sector_default, key="single_sector",
            )
        with c6:
            cap_tier = st.selectbox(
                "시총 구간", ["전체"] + _cap_tiers,
                index=(["전체"] + _cap_tiers).index("Large Cap") if "Large Cap" in _cap_tiers else 0,
                key="single_cap",
            )

        run_single = st.form_submit_button("백테스트 실행", type="primary")

    if run_single:
        # Validate and unpack date range
        if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
            start_d, end_d = date_range
        else:
            st.error("시작일과 종료일을 모두 선택하세요.")
            st.stop()
        cfg = BacktestConfig(
            strategy_key=strat_key,
            start_date=start_d,
            end_date=end_d,
            rebalance_months=rebal,
            n_stocks=n_stocks,
            tc_pct=tc_pct,
            sector=None if sector == "전체" else sector,
            cap_tier=None if cap_tier == "전체" else cap_tier,
        )
        progress = st.progress(0, text="시작…")

        def _cb(done: int, total: int, msg: str) -> None:
            pct = int(done * 100 / max(total, 1))
            progress.progress(min(pct, 100), text=f"[{pct}%] {msg}")

        with st.spinner("백테스트 실행 중…"):
            try:
                result = run_backtest(cfg, progress_callback=_cb)
                st.session_state["single_result"] = result
                progress.progress(100, text="완료")
            except Exception as e:
                st.error(f"실행 실패: {e}")
                st.session_state.pop("single_result", None)

    # Show result if exists
    result = st.session_state.get("single_result")
    if result is not None:
        st.divider()

        # Warnings
        for w in result.warnings:
            st.info(f"ℹ️ {w}")

        # Summary metrics
        m = result.metrics
        spy_m = result.benchmark_metrics.get("SPY", {})
        qqq_m = result.benchmark_metrics.get("QQQ", {})
        st.subheader(f"{result.strategy.name} — 백테스트 결과")
        cols = st.columns(6)
        cols[0].metric(
            "누적 수익률", f"{m.get('total_return_pct', 0):+.1f}%",
            delta=f"vs SPY {m.get('total_return_pct', 0) - spy_m.get('total_return_pct', 0):+.1f}%p",
        )
        cols[1].metric("CAGR", f"{m.get('cagr_pct', 0):+.2f}%")
        cols[2].metric("Sharpe", f"{m.get('sharpe', 0):.2f}")
        cols[3].metric("변동성", f"{m.get('volatility_pct', 0):.1f}%")
        cols[4].metric("최대 낙폭", f"{m.get('max_drawdown_pct', 0):.1f}%")
        cols[5].metric("기간 승률", f"{m.get('period_win_rate_pct', 0):.0f}%")

        # Benchmark comparison row
        st.caption(
            f"📊 SPY: {spy_m.get('total_return_pct', 0):+.1f}% "
            f"(CAGR {spy_m.get('cagr_pct', 0):+.1f}%)   |   "
            f"QQQ: {qqq_m.get('total_return_pct', 0):+.1f}% "
            f"(CAGR {qqq_m.get('cagr_pct', 0):+.1f}%)"
        )

        # Equity curve
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=result.equity_curve.index, y=result.equity_curve["portfolio"],
            mode="lines", name=result.strategy.name,
            line=dict(color="#60A5FA", width=2.5),
        ))
        if "SPY" in result.equity_curve.columns:
            fig.add_trace(go.Scatter(
                x=result.equity_curve.index, y=result.equity_curve["SPY"],
                mode="lines", name="SPY",
                line=dict(color="#94A3B8", width=1.6, dash="dot"),
            ))
        if "QQQ" in result.equity_curve.columns:
            fig.add_trace(go.Scatter(
                x=result.equity_curve.index, y=result.equity_curve["QQQ"],
                mode="lines", name="QQQ",
                line=dict(color="#F59E0B", width=1.6, dash="dash"),
            ))
        fig.update_layout(
            title="누적 수익률 (초기값 = 1.0)",
            height=420, hovermode="x unified",
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#CBD5E1"),
        )
        fig.update_yaxes(tickformat=".2f")
        st.plotly_chart(fig, width="stretch")

        # Recent rebalances
        with st.expander("리밸런싱 내역 보기"):
            rhs = result.rebalance_history
            if rhs:
                rhs_df = pd.DataFrame([
                    {
                        "리밸런싱 일자": h["date"].strftime("%Y-%m-%d"),
                        "기간 수익률(%)": h["period_return_pct"],
                        "턴오버(%)": h["turnover_pct"],
                        "누적 equity": h["portfolio_equity"],
                        "상위 5종목": ", ".join(h["picks"][:5]),
                    } for h in rhs
                ])
                st.dataframe(rhs_df, width="stretch", hide_index=True)

        # Last rebalance picks (existing)
        if result.rebalance_history:
            last = result.rebalance_history[-1]
            st.caption(f"최근 리밸런싱 ({last['date'].strftime('%Y-%m-%d')}) 선정 종목:")
            st.code(" • ".join(last["picks"]))

        # ── 종료일 기준 선정 종목 ──────────────────────────────────────
        if result.final_picks and result.final_picks_date:
            st.divider()
            fp_date_str = result.final_picks_date.strftime("%Y-%m-%d")
            st.markdown(
                f"""
                <div style="
                    background: linear-gradient(135deg,
                        rgba(34,197,94,0.12) 0%, rgba(59,130,246,0.10) 100%);
                    border: 1px solid rgba(34,197,94,0.35);
                    border-radius: 14px; padding: 18px 22px; margin-top: 4px;">
                  <div style="font-size:0.78rem; font-weight:700; color:#4ADE80;
                               letter-spacing:0.08em; text-transform:uppercase;
                               margin-bottom:6px;">
                    📌 백테스트 종료일 기준 선정 종목
                  </div>
                  <div style="font-size:0.85rem; color:#94A3B8; margin-bottom:14px;">
                    {fp_date_str} · {result.strategy.name} · 상위 {len(result.final_picks)}종목
                  </div>
                  <div style="display:flex; flex-wrap:wrap; gap:8px;">
                    {"".join(
                        f'<span style="background:rgba(34,197,94,0.15);'
                        f'border:1px solid rgba(34,197,94,0.40);'
                        f'border-radius:8px; padding:5px 14px;'
                        f'font-size:0.92rem; font-weight:700; color:#4ADE80;'
                        f'font-family:monospace;">{t}</span>'
                        for t in result.final_picks
                    )}
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


# ═══════════════════════════════════════════════════════════
# TAB 2: Compare Strategies
# ═══════════════════════════════════════════════════════════
with tab_compare:
    st.subheader("복수 전략 비교")
    st.caption("최대 5개 전략을 같은 조건으로 동시 백테스트. 첫 실행은 가격 캐시 워밍으로 시간 소요.")

    _today = date.today()
    _default_start = date(2023, 1, 1)

    with st.form("cmp_form", clear_on_submit=False):
        selected = st.multiselect(
            "비교할 전략 (최대 5개)",
            options=KEYS,
            format_func=lambda k: (
                f"{LABEL_BY_KEY[k]}"
                f" ({_CATEGORY_KO.get(STRAT_BY_KEY[k].category, STRAT_BY_KEY[k].category)})"
            ),
            default=["momentum_12m", "low_volatility", "magic_formula"],
            max_selections=5,
            key="cmp_strats",
        )

        c1, c2 = st.columns([2, 1])
        with c1:
            c_date_range = st.date_input(
                "백테스트 기간",
                value=(_default_start, _today),
                min_value=_today - timedelta(days=15 * 365),
                max_value=_today,
                key="cmp_daterange",
            )
        with c2:
            c_rebal = st.selectbox(
                "리밸런싱", options=[1, 3, 6, 12],
                format_func=lambda n: {1: "월별", 3: "분기", 6: "반기", 12: "연간"}[n],
                index=0, key="cmp_rebal",
            )

        c3, c4, c5, c6 = st.columns(4)
        with c3:
            c_n = st.number_input(
                "보유 종목", min_value=3, max_value=100, value=5, step=1,
                key="cmp_n",
            )
        with c4:
            c_tc = st.number_input(
                "거래비용 (%)", min_value=0.0, max_value=2.0, value=0.3, step=0.05,
                format="%.2f", key="cmp_tc",
            )
        with c5:
            _cmp_sector_options = ["전체"] + _sectors
            _cmp_sector_default = (
                _cmp_sector_options.index("Information Technology")
                if "Information Technology" in _cmp_sector_options else 0
            )
            c_sector = st.selectbox(
                "섹터 필터", _cmp_sector_options,
                index=_cmp_sector_default, key="cmp_sector",
            )
        with c6:
            c_cap = st.selectbox(
                "시총 구간", ["전체"] + _cap_tiers,
                index=(["전체"] + _cap_tiers).index("Large Cap") if "Large Cap" in _cap_tiers else 0,
                key="cmp_cap",
            )

        run_cmp = st.form_submit_button("비교 실행", type="primary")

    if run_cmp and selected:
        if isinstance(c_date_range, (list, tuple)) and len(c_date_range) == 2:
            c_start_d, c_end_d = c_date_range
        else:
            st.error("시작일과 종료일을 모두 선택하세요.")
            st.stop()
        base_cfg = BacktestConfig(
            strategy_key=selected[0],
            start_date=c_start_d,
            end_date=c_end_d,
            rebalance_months=c_rebal,
            n_stocks=c_n, tc_pct=c_tc,
            sector=None if c_sector == "전체" else c_sector,
            cap_tier=None if c_cap == "전체" else c_cap,
        )
        progress = st.progress(0, text="시작…")

        def _cb(done: int, total: int, msg: str) -> None:
            pct = int(done * 100 / max(total, 1))
            progress.progress(min(pct, 100), text=f"[{pct}%] {msg}")

        with st.spinner("다중 백테스트 실행 중…"):
            try:
                results = run_multiple(selected, base_cfg, progress_callback=_cb)
                st.session_state["cmp_results"] = results
                progress.progress(100, text="완료")
            except Exception as e:
                st.error(f"실행 실패: {e}")

    # Show comparison
    cmp_results = st.session_state.get("cmp_results")
    if cmp_results:
        st.divider()

        # Overlay equity curves
        fig = go.Figure()
        palette = ["#60A5FA", "#22C55E", "#EC4899", "#A855F7", "#14B8A6"]
        for i, r in enumerate(cmp_results):
            fig.add_trace(go.Scatter(
                x=r.equity_curve.index, y=r.equity_curve["portfolio"],
                mode="lines", name=r.strategy.name,
                line=dict(color=palette[i % len(palette)], width=2.2),
            ))
        if cmp_results:
            first = cmp_results[0].equity_curve
            if "SPY" in first.columns:
                fig.add_trace(go.Scatter(
                    x=first.index, y=first["SPY"],
                    mode="lines", name="SPY",
                    line=dict(color="#94A3B8", width=1.6, dash="dot"),
                ))
            if "QQQ" in first.columns:
                fig.add_trace(go.Scatter(
                    x=first.index, y=first["QQQ"],
                    mode="lines", name="QQQ",
                    line=dict(color="#F59E0B", width=1.6, dash="dash"),
                ))
        fig.update_layout(
            title="누적 수익률 비교 (초기값 = 1.0)",
            height=440, hovermode="x unified",
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#CBD5E1"),
        )
        st.plotly_chart(fig, width="stretch")

        # Comparison table
        rows = []
        for r in cmp_results:
            rows.append({
                "전략": r.strategy.name,
                "누적%": r.metrics.get("total_return_pct"),
                "CAGR%": r.metrics.get("cagr_pct"),
                "Sharpe": r.metrics.get("sharpe"),
                "변동성%": r.metrics.get("volatility_pct"),
                "최대낙폭%": r.metrics.get("max_drawdown_pct"),
                "승률%": r.metrics.get("period_win_rate_pct"),
            })
        # Benchmarks (SPY & QQQ) from first result — all share the same period
        if cmp_results:
            bmap = cmp_results[0].benchmark_metrics
            for ticker, label in (("SPY", "SPY"), ("QQQ", "QQQ")):
                b = bmap.get(ticker, {})
                rows.append({
                    "전략": f"{label} (벤치마크)",
                    "누적%": b.get("total_return_pct"),
                    "CAGR%": b.get("cagr_pct"),
                    "Sharpe": b.get("sharpe"),
                    "변동성%": b.get("volatility_pct"),
                    "최대낙폭%": b.get("max_drawdown_pct"),
                    "승률%": b.get("period_win_rate_pct"),
                })
        cmp_df = pd.DataFrame(rows)
        st.dataframe(cmp_df, width="stretch", hide_index=True)

        # Final picks per strategy — 가로 비교 레이아웃 (전략 = 컬럼, 종목 = 행)
        results_with_picks = [r for r in cmp_results if r.final_picks]
        if results_with_picks:
            st.divider()
            st.markdown("#### 📌 백테스트 종료일 기준 선정 종목 (전략별 비교)")
            pick_cols = st.columns(len(results_with_picks))
            for i, r in enumerate(results_with_picks):
                fp_date_str = r.final_picks_date.strftime("%Y-%m-%d") if r.final_picks_date else ""
                with pick_cols[i]:
                    st.markdown(
                        f'<div style="margin-bottom:6px;">'
                        f'<span style="font-size:0.82rem;font-weight:700;color:#CBD5E1;">'
                        f'{r.strategy.name}</span><br>'
                        f'<span style="font-size:0.72rem;color:#64748B;">'
                        f'{fp_date_str}</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    for t in r.final_picks:
                        st.markdown(
                            f'<div style="margin-bottom:4px;">'
                            f'<span style="background:rgba(96,165,250,0.15);'
                            f'border:1px solid rgba(96,165,250,0.35);'
                            f'border-radius:6px; padding:3px 10px;'
                            f'font-size:0.88rem; font-weight:700; color:#60A5FA;'
                            f'font-family:monospace; display:inline-block;">{t}</span>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )


# ═══════════════════════════════════════════════════════════
# TAB 3: Strategy Guide
# ═══════════════════════════════════════════════════════════
with tab_guide:
    st.subheader("전략 사전")
    st.caption("각 전략의 선정 규칙과 학술적 배경")

    for s in STRATEGIES:
        if s.category == "price":
            cls = "strategy-info price"
            badge = "🟢 가격 기반 (장기 백테스트 가능)"
        else:
            cls = "strategy-info look"
            badge = "🔵 펀더멘털 PIT (최대 4년 권장)"
        st.markdown(
            f"""
            <div class="{cls}">
              <h4 style="margin:0 0 6px 0;">{s.name}</h4>
              <div style="font-size:0.82rem; color:#94A3B8; margin-bottom:8px;">{badge}</div>
              <div style="font-size:0.9rem; color:#CBD5E1; line-height:1.5;">
                {s.long_description}
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
