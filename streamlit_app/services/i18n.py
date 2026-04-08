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

    # ───────── Common UI ─────────
    "common.refresh":             {"en": "Refresh Data", "ko": "데이터 새로고침"},
    "common.delete":              {"en": "Delete",       "ko": "삭제"},
    "common.clear":               {"en": "Clear",        "ko": "지우기"},
    "common.search":              {"en": "Search",       "ko": "검색"},
    "common.ticker":              {"en": "Ticker",       "ko": "티커"},
    "common.note_optional":       {"en": "Note (optional)", "ko": "메모 (선택)"},
    "common.period":              {"en": "Period",       "ko": "기간"},
    "common.year":                {"en": "Year",         "ko": "연도"},
    "common.month":               {"en": "Month",        "ko": "월"},
    "common.filter_by_ticker":    {"en": "Filter by ticker", "ko": "티커로 필터"},
    "common.no_data":             {"en": "No data available.", "ko": "데이터가 없습니다."},
    "common.loading":             {"en": "Loading…",     "ko": "로드 중..."},

    # ───────── Dashboard ─────────
    "dash.market_indices":        {"en": "Market Indices",       "ko": "주요 지수"},
    "dash.index_charts":          {"en": "Index Charts",         "ko": "지수 차트"},
    "dash.auto_refresh":          {"en": "Auto-refreshing every 5 minutes (market open)",
                                   "ko": "5분마다 자동 새로고침 (장 중)"},
    "dash.heatmap_title":         {"en": "S&P 500 Heatmap",      "ko": "S&P 500 히트맵"},
    "dash.no_heatmap":            {"en": "No heatmap data cached. Go to Heatmap page and click 'Refresh Data'.",
                                   "ko": "캐시된 히트맵 데이터가 없습니다. Heatmap 페이지에서 'Refresh Data'를 누르세요."},
    "dash.portfolio_summary":     {"en": "Portfolio Summary",    "ko": "포트폴리오 요약"},
    "dash.signin_portfolio":      {"en": "🔒 Sign in to see your portfolio summary.",
                                   "ko": "🔒 포트폴리오 요약을 보려면 로그인하세요."},
    "dash.no_portfolio":          {"en": "No portfolios yet. Go to the Portfolio page to create one.",
                                   "ko": "포트폴리오가 없습니다. Portfolio 페이지에서 새로 만들어보세요."},
    "dash.select_portfolios":     {"en": "Select Portfolios",    "ko": "포트폴리오 선택"},
    "dash.select_help":           {"en": "Select at least one portfolio above to see summary and news.",
                                   "ko": "위에서 포트폴리오를 1개 이상 선택해야 요약과 뉴스가 보입니다."},
    "dash.total_value":           {"en": "Total Value",          "ko": "총 평가액"},
    "dash.total_cost":            {"en": "Total Cost",           "ko": "총 매입가"},
    "dash.unrealized_pnl":        {"en": "Unrealized P&L",       "ko": "미실현 손익"},
    "dash.by_stock":              {"en": "By Stock",             "ko": "종목별"},
    "dash.by_sector":             {"en": "By Sector",            "ko": "섹터별"},
    "dash.holdings_news":         {"en": "Holdings News",        "ko": "보유 종목 뉴스"},
    "dash.no_news":               {"en": "No recent news.",      "ko": "최근 뉴스가 없습니다."},

    # ───────── Heatmap page ─────────
    "heat.no_cache":              {"en": "No cached data. Click Refresh to load.",
                                   "ko": "캐시 데이터가 없습니다. Refresh를 눌러 로드하세요."},
    "heat.refreshing":            {"en": "Refreshing heatmap data…",
                                   "ko": "히트맵 데이터 갱신 중..."},
    "heat.no_data_loaded":        {"en": "No heatmap data. Click 'Refresh Data' to load.",
                                   "ko": "히트맵 데이터가 없습니다. 'Refresh Data'를 눌러 로드하세요."},
    "heat.sector_summary":        {"en": "Sector Summary",       "ko": "섹터 요약"},
    "heat.top_movers":            {"en": "Top Movers",           "ko": "급등/급락 종목"},

    # ───────── Stock Detail ─────────
    "sd.recently_viewed":         {"en": "Recently Viewed",      "ko": "최근 본 종목"},
    "sd.recently_empty":          {"en": "Stocks you view will appear here.",
                                   "ko": "본 종목이 여기에 표시됩니다."},
    "sd.search_ticker":           {"en": "Search Ticker",        "ko": "티커 검색"},
    "sd.search_placeholder":      {"en": "e.g. AAPL, NVDA, MSFT", "ko": "예: AAPL, NVDA, MSFT"},
    "sd.select_stock":            {"en": "Select Stock",         "ko": "종목 선택"},
    "sd.enter_directly":          {"en": "Or enter ticker directly", "ko": "또는 티커 직접 입력"},
    "sd.price_chart":             {"en": "Price Chart",          "ko": "가격 차트"},
    "sd.fundamentals":            {"en": "Fundamentals",         "ko": "펀더멘털"},
    "sd.news":                    {"en": "News",                 "ko": "뉴스"},
    "sd.financials":              {"en": "Financials",           "ko": "재무"},
    "sd.no_chart_data":           {"en": "No chart data available.",
                                   "ko": "차트 데이터가 없습니다."},
    "sd.no_news_data":            {"en": "No news available for this ticker.",
                                   "ko": "이 종목의 뉴스가 없습니다."},
    "sd.market_cap":              {"en": "Market Cap",           "ko": "시가총액"},
    "sd.pe":                      {"en": "P/E",                  "ko": "P/E"},
    "sd.div_yield":               {"en": "Dividend Yield",       "ko": "배당 수익률"},
    "sd.fifty_two_high":          {"en": "52W High",             "ko": "52주 최고"},
    "sd.fifty_two_low":           {"en": "52W Low",              "ko": "52주 최저"},
    "sd.price":                   {"en": "Price",                "ko": "가격"},
    "sd.no_match":                {"en": "No matches. Using: {ticker}",
                                   "ko": "검색 결과 없음. 사용: {ticker}"},
    "sd.loading":                 {"en": "Loading {ticker}…",     "ko": "{ticker} 로드 중..."},
    "sd.could_not_load":          {"en": "Could not load data for {ticker}",
                                   "ko": "{ticker} 데이터를 불러올 수 없습니다."},
    "sd.chart_mode":              {"en": "Chart Mode",           "ko": "차트 모드"},
    "sd.bb":                      {"en": "Bollinger Bands",      "ko": "볼린저 밴드"},
    "sd.ma":                      {"en": "MA (20/50)",           "ko": "이동평균 (20/50)"},
    "sd.rsi":                     {"en": "RSI",                  "ko": "RSI"},
    "sd.macd":                    {"en": "MACD",                 "ko": "MACD"},
    "sd.chart_hint":              {"en": "Drag to pan, scroll to zoom, double-click to reset.",
                                   "ko": "드래그로 이동, 스크롤로 확대/축소, 더블클릭으로 초기화."},
    "sd.pe_ratio":                {"en": "P/E Ratio",            "ko": "P/E 비율"},
    "sd.pb_ratio":                {"en": "P/B Ratio",            "ko": "P/B 비율"},
    "sd.eps":                     {"en": "EPS",                  "ko": "EPS"},
    "sd.roe":                     {"en": "ROE",                  "ko": "ROE"},
    "sd.beta":                    {"en": "Beta",                 "ko": "베타"},
    "sd.de_ratio":                {"en": "D/E Ratio",            "ko": "부채비율"},
    "sd.avg_volume":              {"en": "Avg Volume",           "ko": "평균 거래량"},
    "sd.company_desc":            {"en": "Company Description",  "ko": "기업 설명"},
    "sd.recent_news":             {"en": "Recent News — {ticker}",
                                   "ko": "최근 뉴스 — {ticker}"},

    # ───────── Portfolio ─────────
    "pf.portfolio_name":          {"en": "Portfolio Name",       "ko": "포트폴리오 이름"},
    "pf.description_optional":    {"en": "Description (optional)", "ko": "설명 (선택)"},
    "pf.create_btn":              {"en": "Create Portfolio",     "ko": "포트폴리오 만들기"},
    "pf.enter_name":              {"en": "Enter a portfolio name.",
                                   "ko": "포트폴리오 이름을 입력하세요."},
    "pf.create_first":            {"en": "Create your first portfolio above to get started.",
                                   "ko": "위에서 첫 포트폴리오를 만들어 시작하세요."},
    "pf.create_new":              {"en": "➕ Create New Portfolio",
                                   "ko": "➕ 새 포트폴리오 만들기"},
    "pf.delete_portfolio":        {"en": "🗑️ Delete Portfolio",   "ko": "🗑️ 포트폴리오 삭제"},
    "pf.holdings":                {"en": "Holdings",             "ko": "보유 종목"},
    "pf.trades":                  {"en": "Trades",               "ko": "거래"},
    "pf.performance":             {"en": "Performance",          "ko": "성과"},
    "pf.dividends":               {"en": "Dividends",            "ko": "배당"},
    "pf.tax":                     {"en": "Tax",                  "ko": "세금"},
    "pf.holdings_detail":         {"en": "Holdings Detail",      "ko": "보유 종목 상세"},
    "pf.view":                    {"en": "View",                 "ko": "보기"},
    "pf.card_grid":               {"en": "Card Grid",            "ko": "카드 그리드"},
    "pf.table":                   {"en": "Table",                "ko": "테이블"},
    "pf.add_trade":               {"en": "Add Trade",            "ko": "거래 추가"},
    "pf.action":                  {"en": "Action",               "ko": "구분"},
    "pf.buy":                     {"en": "Buy",                  "ko": "매수"},
    "pf.sell":                    {"en": "Sell",                 "ko": "매도"},
    "pf.quantity":                {"en": "Quantity",             "ko": "수량"},
    "pf.price":                   {"en": "Price",                "ko": "가격"},
    "pf.date":                    {"en": "Date",                 "ko": "일자"},
    "pf.notes":                   {"en": "Notes",                "ko": "메모"},
    "pf.submit_trade":            {"en": "Submit Trade",         "ko": "거래 등록"},
    "pf.no_holdings":             {"en": "No holdings yet — add a trade above.",
                                   "ko": "보유 종목이 없습니다. 위에서 거래를 추가하세요."},
    "pf.qty":                     {"en": "Qty",                  "ko": "수량"},
    "pf.avg_cost":                {"en": "Avg Cost",             "ko": "평균 매입가"},
    "pf.current":                 {"en": "Current",              "ko": "현재가"},
    "pf.value":                   {"en": "Value",                "ko": "평가액"},
    "pf.no_trades":               {"en": "No trades yet.",       "ko": "거래 내역이 없습니다."},
    "pf.no_perf":                 {"en": "Not enough data to show performance.",
                                   "ko": "성과를 표시할 데이터가 부족합니다."},
    "pf.no_div":                  {"en": "No dividend data yet.",
                                   "ko": "배당 데이터가 없습니다."},
    "pf.no_tax":                  {"en": "No realized trades to compute tax.",
                                   "ko": "세금 계산을 위한 실현 거래가 없습니다."},
    "pf.trade_history":           {"en": "Trade History",        "ko": "거래 내역"},
    "pf.delete_trade_from":       {"en": "Delete trade from {name}",
                                   "ko": "{name}에서 거래 삭제"},
    "pf.trade_label":             {"en": "Trade",                "ko": "거래"},
    "pf.delete_trade":            {"en": "Delete Trade",         "ko": "거래 삭제"},
    "pf.portfolio_return":        {"en": "Portfolio Return",     "ko": "포트폴리오 수익률"},
    "pf.drawdown_label":          {"en": "**Drawdown** (peak-to-trough decline from running maximum)",
                                   "ko": "**드로다운** (이전 최고치 대비 현재 하락폭)"},
    "pf.commission":              {"en": "Commission ($)",       "ko": "수수료 ($)"},
    "pf.target_portfolio":        {"en": "Target Portfolio",     "ko": "대상 포트폴리오"},
    "pf.type":                    {"en": "Type",                 "ko": "유형"},
    "pf.warn_enter_ticker":       {"en": "Enter a ticker.",      "ko": "티커를 입력하세요."},
    "pf.warn_enter_qty":          {"en": "Enter quantity.",      "ko": "수량을 입력하세요."},
    "pf.warn_price":              {"en": "Price must be > 0.",   "ko": "가격은 0보다 커야 합니다."},
    "pf.added_trade":             {"en": "Added {action} {qty} {ticker} @ ${price:.2f}",
                                   "ko": "{action} {qty} {ticker} @ ${price:.2f} 추가됨"},
    "pf.tax_summary":             {"en": "Tax Summary",          "ko": "세금 요약"},
    "pf.realized_gain":           {"en": "Realized Gain",        "ko": "실현 이익"},
    "pf.realized_loss":           {"en": "Realized Loss",        "ko": "실현 손실"},
    "pf.net":                     {"en": "Net",                  "ko": "순이익"},
    "pf.estimated_tax":           {"en": "Estimated Tax",        "ko": "예상 세금"},
    "pf.div_summary":             {"en": "Dividend Summary",     "ko": "배당 요약"},
    "pf.last_div":                {"en": "Last Dividend",        "ko": "최근 배당"},
    "pf.annual_div":              {"en": "Annual Dividend",      "ko": "연간 배당"},
    "pf.div_yield":               {"en": "Dividend Yield",       "ko": "배당 수익률"},
    "pf.tax_year":                {"en": "Tax Year",             "ko": "세금 연도"},
    "pf.net_gain_loss":           {"en": "Net Gain/Loss",        "ko": "순손익"},
    "pf.realized_gains":          {"en": "Realized Gains",       "ko": "실현 이익"},
    "pf.realized_losses":         {"en": "Realized Losses",      "ko": "실현 손실"},
    "pf.st_gain":                 {"en": "Short-Term Gain",      "ko": "단기 이익"},
    "pf.lt_gain":                 {"en": "Long-Term Gain",       "ko": "장기 이익"},
    "pf.st_loss":                 {"en": "Short-Term Loss",      "ko": "단기 손실"},
    "pf.lt_loss":                 {"en": "Long-Term Loss",       "ko": "장기 손실"},
    "pf.total_annual_div":        {"en": "Total Annual Dividends",
                                   "ko": "연간 총 배당금"},
    "pf.monthly_div":             {"en": "Monthly Dividends",    "ko": "월별 배당금"},
    "pf.month":                   {"en": "Month",                "ko": "월"},
    "pf.dividends_dollar":        {"en": "Dividends ($)",        "ko": "배당금 ($)"},

    # ───────── Sentiment ─────────
    "sent.fg_index":              {"en": "Fear & Greed Index",   "ko": "Fear & Greed 지수"},
    "sent.market_news":           {"en": "Market News",          "ko": "시장 뉴스"},
    "sent.stock_news":            {"en": "Stock News",           "ko": "종목 뉴스"},
    "sent.ai_analysis":           {"en": "AI Analysis",          "ko": "AI 분석"},
    "sent.no_market_news":        {"en": "No market news available.",
                                   "ko": "시장 뉴스가 없습니다."},
    "sent.ticker_for_news":       {"en": "Ticker for news",      "ko": "뉴스를 볼 티커"},
    "sent.no_stock_news":         {"en": "No news available for this ticker.",
                                   "ko": "이 티커의 뉴스가 없습니다."},
    "sent.api_warning":           {"en": "Claude AI analysis uses your API key and may incur costs.",
                                   "ko": "Claude AI 분석은 본인 API 키를 사용하며 비용이 발생할 수 있습니다."},
    "sent.generate_market":       {"en": "Generate AI Market Report",
                                   "ko": "AI 시장 리포트 생성"},
    "sent.generate_stock":        {"en": "Generate AI Stock Report",
                                   "ko": "AI 종목 리포트 생성"},
    "sent.generating":            {"en": "Generating analysis…", "ko": "분석 생성 중..."},
    "sent.fg_now":                {"en": "Now",                  "ko": "현재"},
    "sent.fg_prev_close":         {"en": "Previous Close",       "ko": "전일 종가"},
    "sent.fg_one_week_ago":       {"en": "1 Week Ago",           "ko": "1주 전"},
    "sent.fg_one_month_ago":      {"en": "1 Month Ago",          "ko": "1개월 전"},
    "sent.trending_kw":            {"en": "**🔤 Trending Keywords**",
                                    "ko": "**🔤 트렌딩 키워드**"},
    "sent.trending_kw_for":        {"en": "**🔤 Trending Keywords for {ticker}**",
                                    "ko": "**🔤 {ticker} 트렌딩 키워드**"},
    "sent.dist_title":             {"en": "News Sentiment Distribution",
                                    "ko": "뉴스 감성 분포"},
    "sent.dist_x":                 {"en": "Sentiment Score",
                                    "ko": "감성 점수"},
    "sent.dist_y":                 {"en": "Count", "ko": "건수"},
    "sent.articles_for":           {"en": "{n} articles for {ticker}",
                                    "ko": "{ticker}에 대한 {n}건의 기사"},
    "sent.no_news_for":            {"en": "No news for {ticker}.",
                                    "ko": "{ticker} 뉴스가 없습니다."},
    "sent.avg_sentiment":          {"en": "Avg Sentiment", "ko": "평균 감성"},
    "sent.bullish":                {"en": "Bullish",       "ko": "긍정"},
    "sent.bearish":                {"en": "Bearish",       "ko": "부정"},
    "sent.neutral":                {"en": "Neutral",       "ko": "중립"},
    "sent.vix_score":              {"en": "VIX Score",     "ko": "VIX 점수"},
    "sent.momentum_score":         {"en": "Momentum Score","ko": "모멘텀 점수"},
    "sent.volume_score":           {"en": "Volume Score",  "ko": "거래량 점수"},
    "sent.updated_at":             {"en": "Updated: {ts}", "ko": "갱신: {ts}"},
    "sent.gen_btn":                {"en": "Generate AI Market Report",
                                    "ko": "AI 시장 리포트 생성"},
    "sent.gen_spinner":            {"en": "Generating report with Claude…",
                                    "ko": "Claude로 리포트 생성 중..."},
    "sent.gen_error":              {"en": "AI report unavailable. Check your ANTHROPIC_API_KEY in secrets.",
                                    "ko": "AI 리포트를 사용할 수 없습니다. secrets의 ANTHROPIC_API_KEY를 확인하세요."},
    "sent.analyze_label":          {"en": "Analyze stock news",
                                    "ko": "종목 뉴스 분석"},
    "sent.analyze_btn":            {"en": "Analyze with AI",
                                    "ko": "AI로 분석"},
    "sent.analyze_spinner":        {"en": "Running Claude sentiment analysis…",
                                    "ko": "Claude 감성 분석 실행 중..."},
    "sent.analyze_unavailable":    {"en": "AI analysis unavailable.",
                                    "ko": "AI 분석을 사용할 수 없습니다."},
    "sent.no_headlines":           {"en": "No headlines to analyze.",
                                    "ko": "분석할 헤드라인이 없습니다."},

    # ───────── Calendar ─────────
    "cal.monthly_view":           {"en": "Monthly View",         "ko": "월간 보기"},
    "cal.economic_events":        {"en": "Economic Events",      "ko": "경제 지표"},
    "cal.earnings":               {"en": "Earnings",             "ko": "실적 발표"},
    "cal.no_events":              {"en": "No economic events for this period.",
                                   "ko": "이 기간의 경제 지표가 없습니다."},
    "cal.no_earnings":            {"en": "No earnings data for this period.",
                                   "ko": "이 기간의 실적 발표가 없습니다."},

    # ───────── Screener ─────────
    "scr.refresh_help":           {"en": "Fetch latest fundamentals for all S&P 500 stocks",
                                   "ko": "S&P 500 종목의 최신 펀더멘털을 받아옵니다."},
    "scr.refreshing":             {"en": "Fetching fundamentals (this may take a few minutes)…",
                                   "ko": "펀더멘털 가져오는 중... (몇 분 소요)"},
    "scr.no_data":                {"en": "No stock data available. Please refresh.",
                                   "ko": "종목 데이터가 없습니다. 새로고침하세요."},
    "scr.filters":                {"en": "Filters",              "ko": "필터"},
    "scr.sector":                 {"en": "Sector",               "ko": "섹터"},
    "scr.industry":               {"en": "Industry",             "ko": "산업"},
    "scr.search_placeholder":     {"en": "AAPL, Apple…",         "ko": "AAPL, Apple..."},
    "scr.valuation":              {"en": "Valuation",            "ko": "밸류에이션"},
    "scr.fundamentals":           {"en": "Fundamentals",         "ko": "펀더멘털"},
    "scr.market_cap_volume":      {"en": "Market Cap & Volume",  "ko": "시가총액 & 거래량"},
    "scr.dividend_yield":         {"en": "Dividend Yield",       "ko": "배당 수익률"},
    "scr.market_cap":             {"en": "Market Cap",           "ko": "시가총액"},
    "scr.avg_volume":             {"en": "Avg Volume",           "ko": "평균 거래량"},
    "scr.sort_by":                {"en": "Sort By",              "ko": "정렬 기준"},
    "scr.order":                  {"en": "Order",                "ko": "순서"},
    "scr.descending":             {"en": "Descending",           "ko": "내림차순"},
    "scr.ascending":              {"en": "Ascending",            "ko": "오름차순"},
    "scr.found":                  {"en": "{n} stocks found",     "ko": "{n}개 종목 발견"},
    "scr.sector_dist":            {"en": "Sector Distribution",  "ko": "섹터 분포"},
    "scr.no_dist_data":           {"en": "No data to display.",  "ko": "표시할 데이터가 없습니다."},
    "scr.cached_status":          {"en": "Cached: {n} stocks | Last updated: {ts}",
                                   "ko": "캐시: {n} 종목 | 최종 갱신: {ts}"},
    "scr.cache_warning":          {"en": "No fundamental data cached yet. Click 'Refresh Data' to load (takes 3-5 min, one-time).",
                                   "ko": "캐시된 펀더멘털 데이터가 없습니다. 'Refresh Data'를 눌러 로드하세요 (3-5분 소요, 1회)."},
    "scr.refresh_done":           {"en": "Updated {n} stocks.",  "ko": "{n}개 종목 업데이트됨."},
    "scr.refresh_failed":         {"en": "Refresh failed: {e}",  "ko": "새로고침 실패: {e}"},
    "scr.fetching_progress":      {"en": "Fetching fundamentals… {cur}/{total}",
                                   "ko": "펀더멘털 가져오는 중... {cur}/{total}"},
    "scr.starting":               {"en": "Starting…",            "ko": "시작 중..."},
    "scr.done":                   {"en": "Done! Updated {n} stocks.",
                                   "ko": "완료! {n}개 종목 업데이트됨."},

    # ───────── Compare ─────────
    "cmp.enter_tickers":          {"en": "Enter ticker symbols above to compare.",
                                   "ko": "위에 비교할 티커를 입력하세요."},
    "cmp.min_tickers":            {"en": "Enter at least 2 tickers.",
                                   "ko": "최소 2개의 티커를 입력하세요."},
    "cmp.no_data":                {"en": "Could not load any stock data.",
                                   "ko": "종목 데이터를 불러올 수 없습니다."},
    "cmp.overview":               {"en": "Overview",             "ko": "개요"},
    "cmp.normalized":             {"en": "Normalized Performance (rebased to 100)",
                                   "ko": "정규화 성과 (100 기준)"},
    "cmp.fundamentals_cmp":       {"en": "Fundamentals Comparison",
                                   "ko": "펀더멘털 비교"},
    "cmp.visual_profile":         {"en": "Visual Profile (normalized)",
                                   "ko": "시각화 프로파일 (정규화)"},
    "cmp.enter_2_5_label":        {"en": "Enter 2-5 tickers (comma-separated)",
                                   "ko": "2-5개 티커 입력 (쉼표 구분)"},
    "cmp.return_compare":         {"en": "{period} Return Comparison",
                                   "ko": "{period} 수익률 비교"},
    "cmp.radar_caption":          {"en": "Each metric is normalized 0-1 across the selected tickers. Larger area = stronger relative profile.",
                                   "ko": "각 지표는 선택한 티커 간 0~1로 정규화됩니다. 면적이 클수록 상대 프로파일이 강합니다."},

    # ───────── Watchlist ─────────
    "wl.ticker_placeholder":      {"en": "AAPL",                 "ko": "AAPL"},
    "wl.note_placeholder":        {"en": "Why are you watching?",
                                   "ko": "관심 이유는?"},
    "wl.add":                     {"en": "Add to Watchlist",     "ko": "관심 종목 추가"},
    "wl.empty":                   {"en": "Your watchlist is empty. Add stocks above to start tracking.",
                                   "ko": "관심 종목이 비어 있습니다. 위에서 종목을 추가하세요."},
    "wl.alerts":                  {"en": "Price Alerts",         "ko": "가격 알림"},
    "wl.add_alert":               {"en": "Add Alert",            "ko": "알림 추가"},
    "wl.alert_type":              {"en": "Alert Type",           "ko": "알림 유형"},
    "wl.above":                   {"en": "Above",                "ko": "이상"},
    "wl.below":                   {"en": "Below",                "ko": "이하"},
    "wl.target_price":            {"en": "Target Price",         "ko": "목표 가격"},
    "wl.no_alerts":               {"en": "No alerts set.",       "ko": "설정된 알림이 없습니다."},
    "wl.signin_required":         {"en": "🔒 Sign in to use the watchlist.",
                                   "ko": "🔒 관심 종목을 사용하려면 로그인하세요."},
    "wl.tab_watchlist":           {"en": "⭐ Watchlist", "ko": "⭐ 관심 종목"},
    "wl.tab_alerts":              {"en": "🔔 Alerts",   "ko": "🔔 알림"},
    "wl.add_to":                  {"en": "➕ Add to Watchlist", "ko": "➕ 관심 종목 추가"},
    "wl.add_btn":                 {"en": "Add",         "ko": "추가"},
    "wl.added_msg":               {"en": "Added {ticker}", "ko": "{ticker} 추가됨"},
    "wl.already_in":              {"en": "{ticker} is already in your watchlist.",
                                   "ko": "{ticker} 은(는) 이미 관심 종목입니다."},
    "wl.current":                 {"en": "Current",     "ko": "현재가"},
    "wl.day":                     {"en": "Day",         "ko": "일간"},
    "wl.added_at":                {"en": "Added @",     "ko": "추가 시점"},
    "wl.since":                   {"en": "Since",       "ko": "이후"},
    "wl.remove":                  {"en": "Remove {ticker}", "ko": "{ticker} 제거"},
    "wl.create_alert_exp":        {"en": "➕ Create Alert", "ko": "➕ 알림 만들기"},
    "wl.condition":               {"en": "Condition",   "ko": "조건"},
    "wl.cond_above":              {"en": "Price above", "ko": "가격 이상"},
    "wl.cond_below":              {"en": "Price below", "ko": "가격 이하"},
    "wl.cond_chg_above":          {"en": "Daily change above (%)",
                                   "ko": "일간 변동 이상 (%)"},
    "wl.cond_chg_below":          {"en": "Daily change below (%)",
                                   "ko": "일간 변동 이하 (%)"},
    "wl.threshold":               {"en": "Threshold",   "ko": "임계값"},
    "wl.create_btn":              {"en": "Create Alert", "ko": "알림 생성"},
    "wl.alert_created":           {"en": "Alert created for {ticker}",
                                   "ko": "{ticker} 알림 생성됨"},
    "wl.no_alerts_yet":           {"en": "No alerts yet. Create one above.",
                                   "ko": "알림이 없습니다. 위에서 추가하세요."},
    "wl.summary":                 {"en": "**Active: {active}** | **Triggered: {triggered}**",
                                   "ko": "**활성: {active}** | **발동됨: {triggered}**"},
    "wl.active_alerts":           {"en": "### 🟢 Active Alerts",
                                   "ko": "### 🟢 활성 알림"},
    "wl.triggered_alerts":        {"en": "### 🔴 Triggered Alerts",
                                   "ko": "### 🔴 발동된 알림"},
    "wl.delete":                  {"en": "Delete",      "ko": "삭제"},
    "wl.reactivate":              {"en": "Reactivate",  "ko": "재활성화"},
    "wl.toast_rose_above":        {"en": "rose above",   "ko": "이상으로 상승"},
    "wl.toast_fell_below":        {"en": "fell below",   "ko": "이하로 하락"},
    "wl.toast_chg_exceeded":      {"en": "daily change exceeded",
                                   "ko": "일간 변동 초과"},
    "wl.toast_chg_below":         {"en": "daily change fell below",
                                   "ko": "일간 변동 미만"},

    # ───────── Home (login screen elements) ─────────
    "home.signin":                {"en": "Sign in with Google",  "ko": "Google로 로그인"},
    "home.claim_yes":             {"en": "Claim them as mine",   "ko": "내 것으로 가져오기"},
    "home.claim_no":              {"en": "Ignore (start fresh)", "ko": "무시 (새로 시작)"},
    "home.claim_later":           {"en": "You can claim them later by visiting this page again.",
                                   "ko": "나중에 이 페이지에 다시 방문해서 가져올 수 있습니다."},
    "home.loading_indices":       {"en": "Loading market indices…",
                                   "ko": "지수 로드 중..."},
    "home.market_indices":        {"en": "Market Indices",       "ko": "주요 지수"},
    "home.top_movers":            {"en": "Top Movers",           "ko": "급등/급락"},
    "home.top_position":          {"en": "Top Position",         "ko": "상위 종목"},
    "home.positions":             {"en": "Positions",            "ko": "보유 수"},
    "home.open_full_portfolio":   {"en": "→ Open full Portfolio page",
                                   "ko": "→ 전체 Portfolio 페이지 열기"},
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
