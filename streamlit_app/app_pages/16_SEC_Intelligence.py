"""SEC Intelligence — 고래 포트폴리오 + 내부자 거래 + 공시 AI 요약."""

from __future__ import annotations

import logging
from datetime import datetime

import pandas as pd
import streamlit as st

from components.ui import inject_css
from services.sec_intelligence_service import (
    WHALE_MANAGERS,
    compute_holdings_diff,
    fetch_and_cache_holdings,
    format_value,
    get_consensus_picks,
    get_metadata_summary,
    get_recent_filings,
    get_filing_text,
    load_cached_holdings,
    load_cached_insider_scan,
    load_prev_cached_holdings,
    scan_large_insider_buys,
)
from services.insider_service import get_insider_trades

inject_css()
logger = logging.getLogger(__name__)

st.markdown("""
<style>
.sec-header {
    background: linear-gradient(135deg, #0a0e27 0%, #0d1f2d 60%, #0a1628 100%);
    border: 1px solid rgba(100,149,237,0.25);
    border-radius: 14px;
    padding: 32px 36px 28px;
    margin-bottom: 28px;
}
.sec-header h2 {
    font-size: 1.8rem; font-weight: 700; color: #F8FAFC;
    margin: 0 0 6px; letter-spacing: -0.4px;
}
.sec-header p { font-size: 0.92rem; color: #94A3B8; margin: 0; }
.sec-badge {
    display: inline-block;
    background: rgba(100,149,237,0.15);
    border: 1px solid rgba(100,149,237,0.4);
    color: #93C5FD; font-size: 0.75rem; font-weight: 600;
    padding: 3px 12px; border-radius: 20px; margin: 0 3px;
}
.whale-card {
    background: rgba(15,23,42,0.7);
    border: 1px solid rgba(203,213,225,0.1);
    border-radius: 10px; padding: 16px 18px;
    margin-bottom: 10px;
}
.whale-name { font-size: 1.0rem; font-weight: 700; color: #E2E8F0; }
.whale-meta { font-size: 0.8rem; color: #64748B; margin-top: 2px; }
.change-new   { color: #34D399; font-weight: 600; }
.change-add   { color: #60A5FA; font-weight: 600; }
.change-red   { color: #FBBF24; font-weight: 600; }
.change-sold  { color: #F87171; font-weight: 600; }
.stat-box {
    background: rgba(15,23,42,0.8);
    border: 1px solid rgba(203,213,225,0.1);
    border-radius: 8px; padding: 14px 18px; text-align: center;
}
.stat-val { font-size: 1.5rem; font-weight: 700; color: #F8FAFC; }
.stat-lbl { font-size: 0.75rem; color: #64748B; margin-top: 2px; }
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="sec-header">
  <h2>🏛️ SEC Intelligence</h2>
  <p>
    SEC EDGAR 공개 데이터 기반 · 고래 포트폴리오 추적 · 내부자 거래 모니터링 · 공시 AI 요약
  </p>
  <div style="margin-top:12px">
    <span class="sec-badge">13F 분기 공시</span>
    <span class="sec-badge">Form 4 내부자</span>
    <span class="sec-badge">8-K / 10-K</span>
    <span class="sec-badge">무료 공개 데이터</span>
  </div>
</div>
""", unsafe_allow_html=True)

# ── 탭 ───────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["🐳 고래 포트폴리오", "👤 내부자 거래", "📄 공시 다이제스트"])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1: 고래 포트폴리오 (13F)
# ══════════════════════════════════════════════════════════════════════════════
with tab1:

    # ── 뷰 선택 ──────────────────────────────────────────────────────────────
    view_cols = st.columns([2, 1])
    with view_cols[0]:
        view = st.radio(
            "보기 모드",
            ["개별 매니저", "컨센서스 픽"],
            horizontal=True,
            label_visibility="collapsed",
        )
    with view_cols[1]:
        st.caption("ℹ️ 데이터: SEC EDGAR 13F-HR 분기 공시")

    st.divider()

    # ── 컨센서스 픽 뷰 ───────────────────────────────────────────────────────
    if view == "컨센서스 픽":
        st.markdown("#### 여러 고래가 동시에 보유한 종목")

        min_mgr = st.slider("최소 보유 매니저 수", min_value=2, max_value=10, value=3)

        with st.spinner("컨센서스 종목 계산 중..."):
            consensus_df = get_consensus_picks(min_managers=min_mgr)

        if consensus_df.empty:
            st.info("캐시 데이터가 없습니다. 먼저 개별 매니저 데이터를 로드해 주세요.")
        else:
            st.caption(f"총 {len(consensus_df)}개 종목이 {min_mgr}명 이상 보유")
            display_df = consensus_df.copy()
            display_df.insert(0, "#", range(1, len(display_df) + 1))
            display_df = display_df.rename(columns={
                "ticker": "Ticker",
                "company": "회사명",
                "manager_count": "보유 매니저 수",
                "managers": "매니저",
                "total_value_M": "합산 가치 (M$)",
            })
            st.dataframe(display_df, use_container_width=True, hide_index=True, height=450)

    # ── 개별 매니저 뷰 ───────────────────────────────────────────────────────
    else:
        col_sel, col_btn = st.columns([3, 1])
        with col_sel:
            manager_options = {
                f"{m['manager']} ({m['name']})": m["cik"] for m in WHALE_MANAGERS
            }
            selected_label = st.selectbox(
                "매니저 선택",
                list(manager_options.keys()),
                label_visibility="collapsed",
            )
        selected_cik = manager_options[selected_label]
        selected_meta = next(m for m in WHALE_MANAGERS if m["cik"] == selected_cik)

        with col_btn:
            fetch_btn = st.button("🔄 최신 데이터 로드", use_container_width=True)

        # 데이터 로드
        if fetch_btn:
            with st.spinner(f"{selected_meta['manager']} 13F 수집 중... (10~30초 소요)"):
                try:
                    holdings_data = fetch_and_cache_holdings(selected_cik, force=True)
                    if holdings_data:
                        st.success(f"✅ {holdings_data['period']} 기준 데이터 로드 완료")
                    else:
                        st.error("13F 데이터를 가져오지 못했습니다. 잠시 후 다시 시도해 주세요.")
                except Exception as e:
                    st.error(f"오류: {e}")
        else:
            holdings_data = load_cached_holdings(selected_cik)

        if not holdings_data:
            st.info(
                f"**{selected_meta['manager']}**의 캐시 데이터가 없습니다.\n\n"
                "'🔄 최신 데이터 로드' 버튼을 눌러 SEC EDGAR에서 직접 가져오세요."
            )
        else:
            holdings = holdings_data.get("holdings", [])
            period = holdings_data.get("period", "")
            filed = holdings_data.get("filed_date", "")
            total_val_k = sum(h.get("value_k", 0) for h in holdings)

            # ── 매니저 요약 ────────────────────────────────────────────────
            m_cols = st.columns(4)
            stats = [
                ("보유 종목 수", f"{len(holdings):,}"),
                ("포트폴리오 규모", format_value(total_val_k)),
                ("기준일", period),
                ("공시일", filed),
            ]
            for col, (lbl, val) in zip(m_cols, stats):
                with col:
                    st.markdown(f"""
                    <div class="stat-box">
                        <div class="stat-val">{val}</div>
                        <div class="stat-lbl">{lbl}</div>
                    </div>
                    """, unsafe_allow_html=True)

            st.markdown("")

            # ── 하위 탭: 보유 현황 / 변화 ─────────────────────────────────
            sub1, sub2 = st.tabs(["📋 보유 현황", "🔀 전분기 대비 변화"])

            with sub1:
                top_n = st.slider("상위 종목 수", 10, min(100, len(holdings)), 20, key="top_n_slider")
                top_holdings = holdings[:top_n]

                rows = []
                for i, h in enumerate(top_holdings, 1):
                    rows.append({
                        "#": i,
                        "Ticker": h.get("ticker") or "—",
                        "회사명": h["company"][:35],
                        "보유 주수": f"{h.get('shares', 0):,}",
                        "평가액": format_value(h.get("value_k", 0)),
                        "비중": f"{h.get('pct_port', 0):.1f}%",
                    })

                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=500)

            with sub2:
                prev_data = load_prev_cached_holdings(selected_cik)
                if not prev_data:
                    st.info(
                        "이전 분기 데이터가 없습니다. "
                        "2분기 이상의 캐시가 쌓이면 QoQ 변화를 확인할 수 있습니다."
                    )
                else:
                    diff = compute_holdings_diff(holdings_data, prev_data)
                    prev_period = prev_data.get("period", "이전 분기")

                    d_cols = st.columns(4)
                    diff_stats = [
                        ("🆕 신규", len(diff["new"]), "change-new"),
                        ("📈 증가", len(diff["added"]), "change-add"),
                        ("📉 감소", len(diff["reduced"]), "change-red"),
                        ("🔴 청산", len(diff["sold"]), "change-sold"),
                    ]
                    for col, (lbl, cnt, cls) in zip(d_cols, diff_stats):
                        with col:
                            st.markdown(f"""
                            <div class="stat-box">
                                <div class="stat-val {cls}">{cnt}</div>
                                <div class="stat-lbl">{lbl}</div>
                            </div>
                            """, unsafe_allow_html=True)

                    st.caption(f"비교: {period} vs {prev_period}")
                    st.markdown("")

                    if diff["new"]:
                        st.markdown("##### 🆕 신규 매수")
                        new_rows = [{
                            "Ticker": h.get("ticker") or "—",
                            "회사명": h["company"][:35],
                            "평가액": format_value(h.get("value_k", 0)),
                            "비중": f"{h.get('pct_port', 0):.1f}%",
                        } for h in diff["new"][:20]]
                        st.dataframe(pd.DataFrame(new_rows), use_container_width=True, hide_index=True)

                    if diff["added"]:
                        st.markdown("##### 📈 비중 확대")
                        add_rows = [{
                            "Ticker": h.get("ticker") or "—",
                            "회사명": h["company"][:35],
                            "변화율": f"+{h.get('pct_change', 0):.0f}%",
                            "평가액": format_value(h.get("value_k", 0)),
                        } for h in diff["added"][:20]]
                        st.dataframe(pd.DataFrame(add_rows), use_container_width=True, hide_index=True)

                    if diff["sold"]:
                        st.markdown("##### 🔴 청산")
                        sold_rows = [{
                            "Ticker": h.get("ticker") or "—",
                            "회사명": h["company"][:35],
                            "이전 평가액": format_value(h.get("value_k", 0)),
                        } for h in diff["sold"][:20]]
                        st.dataframe(pd.DataFrame(sold_rows), use_container_width=True, hide_index=True)

    # ── 메타 정보 ─────────────────────────────────────────────────────────────
    with st.expander("ℹ️ 데이터 현황 / 매니저 목록"):
        meta = get_metadata_summary()
        thirteenf_meta = meta.get("13f", {})

        mgr_rows = []
        for m in WHALE_MANAGERS:
            cik_meta = thirteenf_meta.get(m["cik"], {})
            mgr_rows.append({
                "매니저": m["manager"],
                "펀드": m["name"],
                "스타일": m["style"],
                "최신 기준일": cik_meta.get("latest_period", "—"),
                "공시일": cik_meta.get("filed_date", "—"),
            })
        st.dataframe(pd.DataFrame(mgr_rows), use_container_width=True, hide_index=True)
        st.caption("🔄 13F는 분기별 자동 수집 (매년 1/4/7/10월). 수동 로드는 개별 버튼 사용.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2: 내부자 거래 (Form 4)
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    ins_view = st.radio(
        "내부자 거래 보기",
        ["📡 최근 대량 매수 스캔", "🔍 종목별 조회"],
        horizontal=True,
        label_visibility="collapsed",
    )
    st.divider()

    # ── 대량 매수 스캔 뷰 ─────────────────────────────────────────────────────
    if ins_view == "📡 최근 대량 매수 스캔":
        scan_cols = st.columns([3, 1])
        with scan_cols[0]:
            st.markdown("#### S&P 500 내부자 대량 매수 (최근 7일)")
        with scan_cols[1]:
            rescan_btn = st.button("🔄 다시 스캔", use_container_width=True)

        min_val_opt = st.select_slider(
            "최소 매수 금액",
            options=[50_000, 100_000, 250_000, 500_000, 1_000_000],
            value=100_000,
            format_func=lambda x: f"${x:,}",
        )

        if rescan_btn:
            from scripts.fetch_sec_intelligence import _SP500_TOP
            with st.spinner("내부자 거래 스캔 중... (1~3분 소요)"):
                try:
                    scan_df = scan_large_insider_buys(_SP500_TOP, days=7, min_value_usd=min_val_opt)
                    if not scan_df.empty:
                        st.session_state["_insider_scan_df"] = scan_df
                        st.success(f"✅ 대량 매수 {len(scan_df)}건 발견")
                    else:
                        st.session_state["_insider_scan_df"] = pd.DataFrame()
                        st.info("최근 7일간 기준 이상 매수 없음")
                except Exception as e:
                    st.error(f"스캔 오류: {e}")

        # 캐시된 결과 또는 세션 결과 표시
        if "_insider_scan_df" in st.session_state and not st.session_state["_insider_scan_df"].empty:
            scan_df = st.session_state["_insider_scan_df"]
        else:
            cached_rows = load_cached_insider_scan()
            scan_df = pd.DataFrame(cached_rows) if cached_rows else pd.DataFrame()

        if scan_df.empty:
            st.info(
                "스캔 결과가 없습니다.\n\n"
                "- '🔄 다시 스캔' 버튼으로 실시간 조회\n"
                "- 또는 스케줄러(`fetch_sec_intelligence.py`)가 매일 자동 갱신합니다."
            )
        else:
            # 금액 필터 적용
            if "Value ($)" in scan_df.columns:
                filtered = scan_df[scan_df["Value ($)"].fillna(0) >= min_val_opt].copy()
            else:
                filtered = scan_df.copy()

            if filtered.empty:
                st.info(f"${min_val_opt:,} 이상 매수 없음")
            else:
                st.caption(f"총 {len(filtered)}건")
                display_cols = ["Ticker", "Date", "Insider", "Role", "Type", "Shares", "Price", "Value ($)"]
                display_cols = [c for c in display_cols if c in filtered.columns]
                if "Value ($)" in filtered.columns:
                    filtered["Value ($)"] = filtered["Value ($)"].apply(
                        lambda x: f"${x:,.0f}" if pd.notna(x) and x else "—"
                    )
                if "Price" in filtered.columns:
                    filtered["Price"] = filtered["Price"].apply(
                        lambda x: f"${x:.2f}" if pd.notna(x) and x else "—"
                    )
                if "Shares" in filtered.columns:
                    filtered["Shares"] = filtered["Shares"].apply(
                        lambda x: f"{x:,.0f}" if pd.notna(x) and x else "—"
                    )
                st.dataframe(filtered[display_cols], use_container_width=True, hide_index=True, height=480)

            if "fetched_at" in scan_df.columns:
                ts = scan_df["fetched_at"].iloc[0]
                if ts:
                    st.caption(f"마지막 스캔: {str(ts)[:16]} UTC")

    # ── 종목별 조회 뷰 ───────────────────────────────────────────────────────
    else:
        ins_ticker = st.text_input(
            "종목 티커",
            value="AAPL",
            max_chars=10,
            placeholder="AAPL, MSFT, NVDA ...",
            label_visibility="collapsed",
        ).upper().strip()

        look_back = st.slider("조회 기간 (일)", 30, 365, 180, key="insider_days")

        if ins_ticker:
            with st.spinner(f"{ins_ticker} 내부자 거래 조회 중..."):
                try:
                    ins_df = get_insider_trades(ins_ticker, days=look_back)
                except Exception as e:
                    ins_df = pd.DataFrame()
                    st.error(f"조회 실패: {e}")

            if ins_df.empty:
                st.info(f"**{ins_ticker}** — 최근 {look_back}일간 내부자 거래 없음 (또는 데이터 없음)")
            else:
                buy_val = ins_df[ins_df["Type"] == "Buy"]["Value ($)"].sum()
                sell_val = ins_df[ins_df["Type"] == "Sell"]["Value ($)"].sum()

                s_cols = st.columns(3)
                with s_cols[0]:
                    st.metric("총 거래 건수", f"{len(ins_df)}건")
                with s_cols[1]:
                    st.metric("매수 합계", f"${buy_val:,.0f}" if buy_val else "—")
                with s_cols[2]:
                    st.metric("매도 합계", f"${sell_val:,.0f}" if sell_val else "—")

                st.markdown("")

                # 타입 필터
                types = ins_df["Type"].unique().tolist()
                sel_types = st.multiselect("거래 유형 필터", types, default=types, key="ins_type_filter")
                filtered_ins = ins_df[ins_df["Type"].isin(sel_types)] if sel_types else ins_df

                display_df = filtered_ins.copy()
                if "Value ($)" in display_df.columns:
                    display_df["Value ($)"] = display_df["Value ($)"].apply(
                        lambda x: f"${x:,.0f}" if pd.notna(x) and x else "—"
                    )
                if "Price" in display_df.columns:
                    display_df["Price"] = display_df["Price"].apply(
                        lambda x: f"${x:.2f}" if pd.notna(x) and x else "—"
                    )
                if "Shares" in display_df.columns:
                    display_df["Shares"] = display_df["Shares"].apply(
                        lambda x: f"{x:,.0f}" if pd.notna(x) and x else "—"
                    )

                st.dataframe(display_df, use_container_width=True, hide_index=True, height=480)
                st.caption(f"출처: SEC EDGAR Form 4 · {ins_ticker} · 최근 {look_back}일")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3: 공시 다이제스트 (AI 요약)
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.markdown("#### SEC 공시 목록 + AI 요약")
    st.caption("8-K · 10-K · 10-Q 공시를 조회하고 AI 요약을 생성합니다.")

    fdig_cols = st.columns([2, 1, 1])
    with fdig_cols[0]:
        filing_ticker = st.text_input(
            "종목",
            value="AAPL",
            max_chars=10,
            placeholder="AAPL ...",
            key="filing_ticker",
            label_visibility="collapsed",
        ).upper().strip()
    with fdig_cols[1]:
        form_filter = st.multiselect(
            "공시 유형",
            ["8-K", "10-K", "10-Q"],
            default=["8-K", "10-K", "10-Q"],
            label_visibility="collapsed",
        )
    with fdig_cols[2]:
        load_filings_btn = st.button("📋 공시 조회", use_container_width=True)

    if load_filings_btn and filing_ticker:
        with st.spinner(f"{filing_ticker} 공시 목록 조회 중..."):
            try:
                filings_df = get_recent_filings(
                    filing_ticker,
                    form_types=tuple(form_filter) if form_filter else ("8-K", "10-K", "10-Q"),
                )
                st.session_state["_filings_df"] = filings_df
                st.session_state["_filings_ticker"] = filing_ticker
            except Exception as e:
                st.error(f"공시 조회 실패: {e}")
                filings_df = pd.DataFrame()

    filings_df = st.session_state.get("_filings_df", pd.DataFrame())
    current_filing_ticker = st.session_state.get("_filings_ticker", "")

    if filings_df.empty:
        st.info("종목 티커를 입력하고 '📋 공시 조회' 버튼을 눌러주세요.")
    else:
        st.caption(f"**{current_filing_ticker}** — 최근 {len(filings_df)}건 공시")

        for _, row in filings_df.iterrows():
            form = row.get("Form", "")
            filed = row.get("Filed", "")
            desc = row.get("Description", form)
            acc_no = row.get("Accession", "")
            url = row.get("URL", "")

            form_icon = {"8-K": "📢", "10-K": "📊", "10-Q": "📋"}.get(form, "📄")

            with st.expander(f"{form_icon} **{form}** · {filed} — {desc[:60]}"):
                col_link, col_ai = st.columns([2, 1])
                with col_link:
                    if url:
                        st.markdown(f"[🔗 EDGAR 원문 보기]({url})")
                with col_ai:
                    ai_key = f"_ai_summary_{acc_no}"
                    summarize_btn = st.button(
                        "🤖 AI 요약 생성",
                        key=f"sum_btn_{acc_no}",
                        help="Claude API 사용 (비용 발생) — 클릭 시 실행",
                    )

                if summarize_btn:
                    with st.spinner("공시 본문 로드 + AI 요약 중..."):
                        try:
                            text = get_filing_text(current_filing_ticker, acc_no)
                            if not text:
                                st.warning("본문을 가져오지 못했습니다.")
                            else:
                                from core.llm_provider import LLMProvider
                                llm = LLMProvider()
                                prompt = (
                                    f"다음은 {current_filing_ticker}의 SEC {form} 공시 내용입니다.\n\n"
                                    f"{text[:6000]}\n\n"
                                    "다음을 한국어로 간결하게 요약해 주세요:\n"
                                    "1. 핵심 이슈 (2~3줄)\n"
                                    "2. 투자자 관점에서 주목할 점 (불릿 2~3개)\n"
                                    "3. 리스크 또는 기회 요인 (불릿 2~3개)"
                                )
                                summary = llm.complete(prompt, max_tokens=800)
                                st.session_state[ai_key] = summary
                        except Exception as e:
                            st.error(f"AI 요약 실패: {e}")

                if ai_key in st.session_state:
                    st.markdown("**AI 요약:**")
                    st.markdown(st.session_state[ai_key])

        st.caption("출처: SEC EDGAR 공개 데이터 · AI 요약은 참고용이며 투자 권유가 아닙니다.")
