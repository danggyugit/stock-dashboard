"""Sentiment page — Fear & Greed index + news sentiment analysis."""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

from services.sentiment_service import (
    get_fear_greed, get_market_news, get_stock_news,
    analyze_with_ai, generate_report,
)
from services.auth_service import render_user_sidebar
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

st.set_page_config(page_title="Sentiment", page_icon="🧠", layout="wide")
inject_css()
render_user_sidebar()
render_sidebar_info()
page_header("Market Sentiment", "Fear & Greed index, news sentiment, AI analysis")

# --- Fear & Greed Index ---
st.subheader("Fear & Greed Index")

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
        ("VIX Score", fg.get("vix_score")),
        ("Momentum Score", fg.get("momentum_score")),
        ("Volume Score", fg.get("volume_score")),
    ]

    for name, val in components:
        if val is not None:
            color = "#22C55E" if val >= 60 else "#EAB308" if val >= 40 else "#DC2626"
            st.markdown(f"**{name}**: {val:.1f}/100")
            st.progress(val / 100)
        else:
            st.markdown(f"**{name}**: N/A")

    if fg.get("updated_at"):
        st.caption(f"Updated: {fg['updated_at'][:19]}")

st.markdown("---")

# --- Market News ---
st.subheader("Market News")

news_tab, stock_tab, ai_tab = st.tabs(["Market News", "Stock News", "AI Analysis"])

with news_tab:
    articles = get_market_news()
    if articles:
        # Word cloud from headlines
        headlines = [a.get("headline", "") for a in articles if a.get("headline")]
        wc_bytes = _build_wordcloud(headlines)
        if wc_bytes:
            st.markdown("**🔤 Trending Keywords**")
            st.image(wc_bytes, use_container_width=True)

        # Sentiment distribution
        sentiments = [a.get("sentiment", 0) for a in articles]
        fig = px.histogram(
            x=sentiments, nbins=20,
            labels={"x": "Sentiment Score", "y": "Count"},
            title="News Sentiment Distribution",
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
        st.caption("No market news available.")

with stock_tab:
    ticker = st.text_input("Ticker", value="NVDA", key="sentiment_ticker").upper().strip()
    if ticker:
        articles = get_stock_news(ticker)
        if articles:
            st.caption(f"{len(articles)} articles for {ticker}")

            # Word cloud
            headlines = [a.get("headline", "") for a in articles if a.get("headline")]
            wc_bytes = _build_wordcloud(headlines)
            if wc_bytes:
                st.markdown(f"**🔤 Trending Keywords for {ticker}**")
                st.image(wc_bytes, use_container_width=True)

            # Sentiment summary
            scores = [a.get("sentiment", 0) for a in articles]
            avg = sum(scores) / len(scores) if scores else 0
            bullish = sum(1 for s in scores if s > 0.3)
            bearish = sum(1 for s in scores if s < -0.3)
            neutral = len(scores) - bullish - bearish

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Avg Sentiment", f"{avg:+.2f}")
            c2.metric("Bullish", bullish)
            c3.metric("Neutral", neutral)
            c4.metric("Bearish", bearish)

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
            st.caption(f"No news for {ticker}.")

with ai_tab:
    st.caption("Claude AI analysis uses your API key and may incur costs.")

    if st.button("Generate AI Market Report"):
        with st.spinner("Generating report with Claude..."):
            report = generate_report()
        if report:
            st.markdown(report)
        else:
            st.warning("AI report unavailable. Check your ANTHROPIC_API_KEY in secrets.")

    st.markdown("---")
    ai_ticker = st.text_input("Analyze stock news", value="AAPL", key="ai_ticker").upper()
    if st.button("Analyze with AI"):
        articles = get_stock_news(ai_ticker)
        headlines = [a["headline"] for a in articles[:20] if a.get("headline")]
        if headlines:
            with st.spinner("Running Claude sentiment analysis..."):
                results = analyze_with_ai(headlines)
            if results:
                df = pd.DataFrame(results)
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.warning("AI analysis unavailable.")
        else:
            st.warning("No headlines to analyze.")
