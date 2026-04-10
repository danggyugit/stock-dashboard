"""Sentiment page — Fear & Greed index + news sentiment analysis."""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

from services.sentiment_service import (
    get_fear_greed, get_market_news, get_stock_news,
    analyze_with_ai, generate_report,
    get_vix_history, get_sector_returns, get_market_breadth, get_risk_on_off,
)
from services.auth_service import render_user_sidebar
from services.i18n import t as tr
from components.ui import inject_css, page_header, render_sidebar_info

import io
import re

# Optional dependency - graceful fallback if not installed
try:
    import matplotlib.pyplot as plt
    from wordcloud import WordCloud, STOPWORDS
    _WORDCLOUD_AVAILABLE = True
except ImportError:
    _WORDCLOUD_AVAILABLE = False
    STOPWORDS = set()

_FINANCE_STOPWORDS = set(STOPWORDS) | {
    "stock", "stocks", "share", "shares", "market", "markets", "company",
    "companies", "say", "says", "said", "report", "reports", "year", "years",
    "new", "may", "would", "could", "one", "two", "first", "second", "us",
    "according", "yahoo", "finance", "video", "today", "week", "month",
}


def _build_wordcloud(headlines: list[str]) -> bytes | None:
    """Build a word cloud image from headlines. Returns PNG bytes."""
    if not _WORDCLOUD_AVAILABLE:
        return None
    text = " ".join(headlines)
    text = re.sub(r"[^a-zA-Z\s]", " ", text)
    if not text.strip():
        return None
    try:
        wc = WordCloud(
            width=1200, height=400,
            background_color=None, mode="RGBA",
            colormap="Blues",
            stopwords=_FINANCE_STOPWORDS,
            max_words=80, relative_scaling=0.5,
            min_font_size=10, prefer_horizontal=0.9,
        ).generate(text)
        buf = io.BytesIO()
        fig, ax = plt.subplots(figsize=(12, 4), facecolor="none")
        ax.imshow(wc, interpolation="bilinear")
        ax.axis("off")
        fig.patch.set_alpha(0)
        plt.savefig(buf, format="png", bbox_inches="tight",
                    facecolor="none", transparent=True, dpi=100)
        plt.close(fig)
        buf.seek(0)
        return buf.getvalue()
    except Exception:
        return None

page_header("page.sentiment.title", "page.sentiment.subtitle")

# --- Fear & Greed Index ---
st.subheader(tr("sent.fg_index"))

fg = get_fear_greed()

col1, col2 = st.columns([1, 2])

with col1:
    score = fg.get("score", 50)
    label = fg.get("label", "Neutral")

    # Gauge chart
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=score,
        title={"text": label, "font": {"size": 24}},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1},
            "bar": {"color": "#3B82F6"},
            "steps": [
                {"range": [0, 20], "color": "#DC2626"},
                {"range": [20, 40], "color": "#F97316"},
                {"range": [40, 60], "color": "#EAB308"},
                {"range": [60, 80], "color": "#84CC16"},
                {"range": [80, 100], "color": "#22C55E"},
            ],
            "threshold": {
                "line": {"color": "white", "width": 4},
                "thickness": 0.75, "value": score,
            },
        },
    ))
    fig.update_layout(
        height=300, margin=dict(l=20, r=20, t=50, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True)

with col2:
    # Component scores
    components = [
        (tr("sent.vix_score"), fg.get("vix_score")),
        (tr("sent.momentum_score"), fg.get("momentum_score")),
        (tr("sent.volume_score"), fg.get("volume_score")),
    ]

    for name, val in components:
        if val is not None:
            color = "#22C55E" if val >= 60 else "#EAB308" if val >= 40 else "#DC2626"
            st.markdown(f"**{name}**: {val:.1f}/100")
            st.progress(val / 100)
        else:
            st.markdown(f"**{name}**: N/A")

    if fg.get("updated_at"):
        st.caption(tr("sent.updated_at", ts=fg['updated_at'][:19]))

st.markdown("---")

# ═══════════════════════════════════════════════════════════
# VIX Trend + Market Breadth (side by side)
# ═══════════════════════════════════════════════════════════
vix_col, breadth_col = st.columns(2)

with vix_col:
    st.subheader("📉 VIX Trend (90D)")
    vix_df = get_vix_history(90)
    if not vix_df.empty:
        fig_vix = go.Figure()
        fig_vix.add_trace(go.Scatter(
            x=vix_df["date"], y=vix_df["VIX"],
            line=dict(color="#EF4444", width=2),
            fill="tozeroy", fillcolor="rgba(239,68,68,0.1)",
            hovertemplate="%{x|%m/%d}<br>VIX: %{y:.1f}<extra></extra>",
        ))
        # Reference lines
        fig_vix.add_hline(y=20, line_dash="dash", line_color="#64748b",
                          annotation_text="20 (Neutral)", annotation_position="bottom right",
                          annotation_font_size=10, annotation_font_color="#64748b")
        fig_vix.add_hline(y=30, line_dash="dash", line_color="#F59E0B",
                          annotation_text="30 (Fear)", annotation_position="bottom right",
                          annotation_font_size=10, annotation_font_color="#F59E0B")
        fig_vix.update_layout(
            height=280, margin=dict(l=0, r=0, t=10, b=0),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(gridcolor="rgba(100,116,139,0.2)"),
            xaxis=dict(gridcolor="rgba(100,116,139,0.1)"),
            showlegend=False,
        )
        st.plotly_chart(fig_vix, use_container_width=True)
        latest_vix = vix_df["VIX"].iloc[-1]
        _vix_clr = "#22C55E" if latest_vix < 20 else ("#EAB308" if latest_vix < 30 else "#EF4444")
        _vix_lbl = "Low Fear" if latest_vix < 20 else ("Elevated" if latest_vix < 30 else "High Fear")
        st.markdown(
            f'<div style="text-align:center;font-size:1.3rem;font-weight:700;color:{_vix_clr};">'
            f'VIX {latest_vix:.1f} — {_vix_lbl}</div>',
            unsafe_allow_html=True,
        )
    else:
        st.caption("VIX data unavailable")

with breadth_col:
    st.subheader("📊 Market Breadth")
    breadth = get_market_breadth()
    if breadth:
        spread_s = breadth["spread_series"]
        fig_br = go.Figure()
        colors = ["#22C55E" if v >= 0 else "#EF4444" for v in spread_s.values]
        fig_br.add_trace(go.Bar(
            x=spread_s.index, y=spread_s.values,
            marker_color=colors,
            hovertemplate="%{x|%m/%d}<br>%{y:+.1f}%<extra></extra>",
        ))
        fig_br.add_hline(y=0, line_color="#64748b", line_width=1)
        fig_br.update_layout(
            height=280, margin=dict(l=0, r=0, t=10, b=0),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(gridcolor="rgba(100,116,139,0.2)", ticksuffix="%"),
            xaxis=dict(type="category", gridcolor="rgba(100,116,139,0.1)",
                       tickvals=spread_s.index[::20],
                       ticktext=[d.strftime("%m/%d") for d in spread_s.index[::20]]),
            showlegend=False,
        )
        st.plotly_chart(fig_br, use_container_width=True)
        pct = breadth["above_pct"]
        _br_clr = "#22C55E" if pct > 0 else "#EF4444"
        st.markdown(
            f'<div style="text-align:center;font-size:0.9rem;">'
            f'S&P 500: <b>${breadth["current_close"]:,.0f}</b> vs '
            f'SMA200: <b>${breadth["current_sma200"]:,.0f}</b> '
            f'(<span style="color:{_br_clr};font-weight:700;">{pct:+.1f}%</span>)</div>',
            unsafe_allow_html=True,
        )
    else:
        st.caption("Breadth data unavailable")

st.markdown("---")

# ═══════════════════════════════════════════════════════════
# Sector Returns Heatmap + Risk-On/Off (side by side)
# ═══════════════════════════════════════════════════════════
sector_col, risk_col = st.columns([3, 2])

with sector_col:
    st.subheader("🏭 Sector Returns")
    sector_df = get_sector_returns()
    if not sector_df.empty:
        # Heatmap-style colored table
        fig_sec = go.Figure()
        for col_name, period_label in [("1W %", "1 Week"), ("1M %", "1 Month")]:
            vals = sector_df[col_name]
            colors = [f"rgba(34,197,94,{min(abs(v)/5,1)*0.7})" if v >= 0
                      else f"rgba(239,68,68,{min(abs(v)/5,1)*0.7})" for v in vals]
            fig_sec.add_trace(go.Bar(
                y=sector_df["Sector"], x=vals, orientation="h",
                name=period_label, text=[f"{v:+.1f}%" for v in vals],
                textposition="inside", textfont=dict(size=11, color="white"),
                marker_color=colors,
            ))
        fig_sec.update_layout(
            height=380, margin=dict(l=0, r=0, t=10, b=0),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(gridcolor="rgba(100,116,139,0.2)", ticksuffix="%", zeroline=True,
                       zerolinecolor="#64748b"),
            yaxis=dict(autorange="reversed"),
            barmode="group", legend=dict(orientation="h", y=1.05),
        )
        st.plotly_chart(fig_sec, use_container_width=True)
    else:
        st.caption("Sector data unavailable")

with risk_col:
    st.subheader("⚖️ Risk-On / Off")
    risk_df = get_risk_on_off(90)
    if not risk_df.empty:
        fig_risk = go.Figure()
        fig_risk.add_trace(go.Scatter(
            x=risk_df["date"], y=risk_df["XLY/XLP"],
            line=dict(color="#3B82F6", width=2),
            fill="tozeroy", fillcolor="rgba(59,130,246,0.08)",
            hovertemplate="%{x|%m/%d}<br>XLY/XLP: %{y:.3f}<extra></extra>",
        ))
        avg_ratio = risk_df["XLY/XLP"].mean()
        fig_risk.add_hline(y=avg_ratio, line_dash="dash", line_color="#94a3b8",
                           annotation_text=f"Avg {avg_ratio:.3f}",
                           annotation_position="bottom right",
                           annotation_font_size=10, annotation_font_color="#94a3b8")
        fig_risk.update_layout(
            height=340, margin=dict(l=0, r=0, t=10, b=0),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(gridcolor="rgba(100,116,139,0.2)"),
            xaxis=dict(gridcolor="rgba(100,116,139,0.1)"),
            showlegend=False,
        )
        st.plotly_chart(fig_risk, use_container_width=True)
        latest_r = risk_df["XLY/XLP"].iloc[-1]
        _risk_label = "Risk-On 📈" if latest_r > avg_ratio else "Risk-Off 📉"
        _risk_clr = "#22C55E" if latest_r > avg_ratio else "#EF4444"
        st.markdown(
            f'<div style="text-align:center;">'
            f'<span style="font-size:0.8rem;color:#94a3b8;">XLY(경기민감) ÷ XLP(방어) = </span>'
            f'<span style="font-size:1.1rem;font-weight:700;color:{_risk_clr};">'
            f'{latest_r:.3f} {_risk_label}</span></div>',
            unsafe_allow_html=True,
        )
    else:
        st.caption("Risk-On/Off data unavailable")

st.markdown("---")

# --- Market News ---
st.subheader(tr("sent.market_news"))

news_tab, stock_tab, ai_tab = st.tabs([
    tr("sent.market_news"),
    tr("sent.stock_news"),
    tr("sent.ai_analysis"),
])

with news_tab:
    articles = get_market_news()
    if articles:
        # Word cloud from headlines
        headlines = [a.get("headline", "") for a in articles if a.get("headline")]
        wc_bytes = _build_wordcloud(headlines)
        if wc_bytes:
            st.markdown(tr("sent.trending_kw"))
            st.image(wc_bytes, use_container_width=True)

        # Sentiment distribution
        sentiments = [a.get("sentiment", 0) for a in articles]
        fig = px.histogram(
            x=sentiments, nbins=20,
            labels={"x": tr("sent.dist_x"), "y": tr("sent.dist_y")},
            title=tr("sent.dist_title"),
            color_discrete_sequence=["#3B82F6"],
        )
        fig.update_layout(height=250, margin=dict(l=0, r=0, t=40, b=0))
        st.plotly_chart(fig, use_container_width=True)

        # Article list
        for a in articles[:20]:
            sentiment = a.get("sentiment_label", "Neutral")
            badge = {"Bullish": "🟢", "Bearish": "🔴"}.get(sentiment, "⚪")
            score = a.get("sentiment", 0)
            url = a.get("url", "")
            hl = a.get("headline", "")
            source = a.get("source", "")
            if url:
                st.markdown(f"{badge} [{hl}]({url}) — _{source}_ `{score:+.2f}`")
            else:
                st.markdown(f"{badge} {hl} — _{source}_ `{score:+.2f}`")
    else:
        st.caption(tr("sent.no_market_news"))

with stock_tab:
    ticker = st.text_input(tr("common.ticker"), value="NVDA", key="sentiment_ticker").upper().strip()
    if ticker:
        articles = get_stock_news(ticker)
        if articles:
            st.caption(tr("sent.articles_for", n=len(articles), ticker=ticker))

            # Word cloud
            headlines = [a.get("headline", "") for a in articles if a.get("headline")]
            wc_bytes = _build_wordcloud(headlines)
            if wc_bytes:
                st.markdown(tr("sent.trending_kw_for", ticker=ticker))
                st.image(wc_bytes, use_container_width=True)

            # Sentiment summary
            scores = [a.get("sentiment", 0) for a in articles]
            avg = sum(scores) / len(scores) if scores else 0
            bullish = sum(1 for s in scores if s > 0.3)
            bearish = sum(1 for s in scores if s < -0.3)
            neutral = len(scores) - bullish - bearish

            c1, c2, c3, c4 = st.columns(4)
            c1.metric(tr("sent.avg_sentiment"), f"{avg:+.2f}")
            c2.metric(tr("sent.bullish"), bullish)
            c3.metric(tr("sent.neutral"), neutral)
            c4.metric(tr("sent.bearish"), bearish)

            for a in articles[:15]:
                sentiment = a.get("sentiment_label", "Neutral")
                badge = {"Bullish": "🟢", "Bearish": "🔴"}.get(sentiment, "⚪")
                url = a.get("url", "")
                hl = a.get("headline", "")
                source = a.get("source", "")
                if url:
                    st.markdown(f"{badge} [{hl}]({url}) — _{source}_")
                else:
                    st.markdown(f"{badge} {hl} — _{source}_")
        else:
            st.caption(tr("sent.no_news_for", ticker=ticker))

with ai_tab:
    st.caption(tr("sent.api_warning"))

    if st.button(tr("sent.gen_btn")):
        with st.spinner(tr("sent.gen_spinner")):
            report = generate_report()
        if report:
            st.markdown(report)
        else:
            st.warning(tr("sent.gen_error"))

    st.markdown("---")
    ai_ticker = st.text_input(tr("sent.analyze_label"), value="AAPL", key="ai_ticker").upper()
    if st.button(tr("sent.analyze_btn")):
        articles = get_stock_news(ai_ticker)
        headlines = [a["headline"] for a in articles[:20] if a.get("headline")]
        if headlines:
            with st.spinner(tr("sent.analyze_spinner")):
                results = analyze_with_ai(headlines)
            if results:
                df = pd.DataFrame(results)
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.warning(tr("sent.analyze_unavailable"))
        else:
            st.warning(tr("sent.no_headlines"))
