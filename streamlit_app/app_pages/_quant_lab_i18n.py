"""AI Quant Lab translation entries — registered into the global i18n.

The toggle and t() helper now live in services/i18n.py. This file
just defines the page-specific strings and registers them so the
existing call sites (`tr("hero.title")` etc.) keep working.

Re-exports `t` and a no-op `lang_toggle` for backwards compatibility
with the existing import in 2_AI_Quant_Lab.py.
"""

from __future__ import annotations

from services.i18n import t, register_strings  # noqa: F401  (re-export)


def lang_toggle() -> None:
    """Backwards-compat shim — the global sidebar toggle is rendered
    by render_user_sidebar() now, so this is a no-op."""
    return


# ─────────────────────────────────────────────────────────────
# Translation table — merged into services/i18n.STRINGS at import
# ─────────────────────────────────────────────────────────────

_QUANT_LAB_STRINGS: dict[str, dict[str, str]] = {
    # Hero
    "hero.title":      {"en": "AI Quant Lab",
                        "ko": "AI 퀀트 랩"},
    "hero.subtitle":   {"en": "AI quant backtesting & real-time stock recommendations",
                        "ko": "AI 퀀트 백테스팅 & 실시간 종목 추천 플랫폼"},
    "hero.pill.ensemble": {"en": "RF + XGBoost + LightGBM Ensemble",
                           "ko": "RF + XGBoost + LightGBM 앙상블"},
    "hero.pill.features": {"en": "66 Features",
                           "ko": "66개 피처"},
    "hero.pill.cs_norm":  {"en": "Cross-Section Normalization",
                           "ko": "Cross-Section 정규화"},
    "hero.pill.regime":   {"en": "Market Regime · VIX",
                           "ko": "시장 레짐 · VIX"},
    "hero.pill.sector_rs":{"en": "Sector Relative Strength",
                           "ko": "섹터 RS"},
    "hero.pill.surv":     {"en": "Survivorship Bias Fix",
                           "ko": "생존자 편향 보정"},
    "hero.pill.pit":      {"en": "PIT 22 Indicators",
                           "ko": "PIT 22개 지표"},

    # CTA empty state
    "empty.cta_hint":  {"en": "Select your settings above and click <b>🚀 Run Backtest</b> to begin.",
                        "ko": "위 설정 바에서 원하는 조건을 선택한 후 <b>🚀 백테스트 실행</b> 버튼을 눌러주세요."},
    "empty.section":   {"en": "Key Features",
                        "ko": "주요 기능"},
    "feat.ai.title":   {"en": "AI Models",        "ko": "AI 모델"},
    "feat.ai.1":       {"en": "Random Forest prediction",  "ko": "Random Forest 예측"},
    "feat.ai.2":       {"en": "Rolling window training",   "ko": "Rolling 윈도우 학습"},
    "feat.ai.3":       {"en": "Feature importance extraction", "ko": "피처 중요도 추출"},
    "feat.metrics.title": {"en": "Indicators (66)", "ko": "지표 (66종)"},
    "feat.metrics.1":  {"en": "25 technical indicators",   "ko": "기술지표 25종"},
    "feat.metrics.2":  {"en": "25 fundamental metrics",    "ko": "펀더멘털 25종"},
    "feat.metrics.3":  {"en": "Cross-section normalization", "ko": "Cross-section 정규화"},
    "feat.views.title":{"en": "Analytics Views",  "ko": "분석 뷰"},
    "feat.views.1":    {"en": "IC analysis",      "ko": "IC 분석"},
    "feat.views.2":    {"en": "Rebalance history","ko": "리밸런싱 히스토리"},
    "feat.views.3":    {"en": "Indicator heatmap","ko": "지표 히트맵"},
    "feat.live.title": {"en": "Real-time",        "ko": "실시간 추천"},
    "feat.live.1":     {"en": "Picks for a specific date", "ko": "특정일 추천 종목"},
    "feat.live.2":     {"en": "Radar chart",      "ko": "레이더 차트"},
    "feat.live.3":     {"en": "Performance tracking dashboard", "ko": "성과 추적 대시보드"},

    # Settings bar
    "settings.expand":          {"en": "⚙️ Backtest Settings (expand / collapse)",
                                 "ko": "⚙️ 백테스트 설정 펼치기 / 접기"},
    "settings.cap_tier":        {"en": "**📊 Market Cap Tier**",
                                 "ko": "**📊 시가총액 구간 선택**"},
    "settings.cap_help":        {"en": "Large Cap = S&P 500 · Mid Cap = S&P 400 · Small Cap = S&P 600",
                                 "ko": "Large Cap = S&P 500 · Mid Cap = S&P 400 · Small Cap = S&P 600"},
    "settings.sector":          {"en": "**📂 Sector Selection** (multiple allowed)",
                                 "ko": "**📂 분석 섹터 선택** (복수 선택 가능)"},
    "settings.sector_label":    {"en": "GICS sectors",
                                 "ko": "GICS 섹터"},
    "settings.sector_help":     {"en": "Pick the GICS sectors to include",
                                 "ko": "포함할 GICS 섹터를 선택하세요"},
    "settings.universe":        {"en": "Selected universe: **{count}** stocks  ({tier_str})",
                                 "ko": "선택된 유니버스: **{count}**개 종목  ({tier_str})"},
    "settings.tier_n":          {"en": "{tier}: {n}",
                                 "ko": "{tier}: {n}개"},
    "settings.rebal":           {"en": "Rebalance period (months)",
                                 "ko": "리밸런싱 기간 (개월)"},
    "settings.rebal_help":      {"en": "How often to rebalance the portfolio",
                                 "ko": "포트폴리오 리밸런싱 주기"},
    "settings.rolling":         {"en": "Rolling training window (periods)",
                                 "ko": "롤링 학습 윈도우 (기간 수)"},
    "settings.rolling_help":    {"en": "Number of past rebalance periods used to train the model",
                                 "ko": "모델 학습에 사용할 이전 리밸런싱 기간 수"},
    "settings.n_stocks":        {"en": "Number of holdings",
                                 "ko": "투자 종목 수"},
    "settings.tc_pct":          {"en": "Transaction cost (%)",
                                 "ko": "거래비용 (%)"},
    "settings.tc_help":         {"en": "Round-trip total cost (commission + slippage)",
                                 "ko": "왕복 총 거래비용 (수수료 + 슬리피지)"},
    "settings.use_custom_date": {"en": "Specify dates manually",
                                 "ko": "날짜 직접 입력"},
    "settings.start_date":      {"en": "Start date",
                                 "ko": "시작일"},
    "settings.end_date":        {"en": "End date",
                                 "ko": "종료일"},
    "settings.auto_date":       {"en": "📅 Auto: **{sd}** ~ **{ed}** "
                                       "(~{months} months | min {min_test} test runs | "
                                       "1 rebalance = {rebal} months)",
                                 "ko": "📅 자동 설정: **{sd}** ~ **{ed}** "
                                       "(약 {months}개월 | 최소 {min_test}회 테스트 보장 | "
                                       "리밸런싱 1회 = {rebal}개월)"},
    "settings.advanced":        {"en": "**🔬 Advanced Settings**",
                                 "ko": "**🔬 고급 설정**"},
    "settings.min_dollar_vol":  {"en": "Min avg daily $ volume",
                                 "ko": "최소 일평균 거래대금 ($)"},
    "settings.min_dv_help":     {"en": "20-day avg dollar volume; tickers below this are excluded (0 = no filter)",
                                 "ko": "20일 평균 거래대금 기준, 미달 종목 제외 (0 = 필터 없음)"},
    "settings.exec_price":      {"en": "Execution price",
                                 "ko": "체결가 가정"},
    "settings.exec_close":      {"en": "Same-day close",
                                 "ko": "당일 종가"},
    "settings.exec_next_open":  {"en": "Next-day open (T+1)",
                                 "ko": "T+1 시가"},
    "settings.exec_help":       {"en": "Same-day close trades at the rebalance day's close. T+1 open trades the next session's open (more realistic).",
                                 "ko": "당일 종가: 리밸런싱일 종가에 매매 / T+1 시가: 다음 영업일 시가에 매매 (더 현실적)"},
    "settings.surv_fix":        {"en": "Survivorship bias fix",
                                 "ko": "생존자 편향 보정"},
    "settings.surv_help":       {"en": "Restore the actual S&P 500 constituents at each rebalance date (Large Cap only)",
                                 "ko": "S&P 500 변경 이력으로 리밸런싱 시점의 실제 구성 종목 복원 (Large Cap 전용)"},
    "settings.ensemble":        {"en": "Ensemble model (RF + XGBoost + LightGBM)",
                                 "ko": "앙상블 모델 (RF + XGBoost + LightGBM)"},
    "settings.ensemble_help":   {"en": "Average predictions from 3 models for more stable picks. Off = use Random Forest only.",
                                 "ko": "3개 모델의 예측을 평균하여 안정적인 종목 선정. 해제 시 RF 단일 모델 사용."},
    "settings.run_btn":         {"en": "🚀 Run Backtest",
                                 "ko": "🚀 백테스트 실행"},
    "settings.no_sector":       {"en": "Please select at least one sector.",
                                 "ko": "섹터를 선택해주세요."},

    # Spinners / progress
    "spinner.sp1500":           {"en": "Loading S&P 1500 list (Large/Mid/Small Cap)…",
                                 "ko": "S&P 1500 종목 목록 로드 중... (Large/Mid/Small Cap 합산)"},
    "progress.surv_fix":        {"en": "📜 Loading S&P 500 change history (survivorship bias fix)…",
                                 "ko": "📜 S&P 500 변경 이력 로드 중 (생존자 편향 보정)..."},
    "progress.download_prices": {"en": "📡 Downloading price data for {n} tickers…",
                                 "ko": "📡 {n}개 종목 가격 데이터 다운로드 중..."},
    "progress.prices_done":     {"en": "✅ {n} tickers loaded ({extra} historical delisted included). Loading fundamentals…",
                                 "ko": "✅ {n}개 종목 ({extra}개 역사적 퇴출 종목 포함). 펀더멘털 로드 중..."},
    "progress.fund_done":       {"en": "✅ Fundamentals: {ok}/{n}. Loading PIT quarterly statements…",
                                 "ko": "✅ 펀더멘털 완료: {ok}/{n}개. PIT 분기 재무제표 수집 중..."},
    "progress.pit_loading":     {"en": "📋 Collecting quarterly statements ({n} tickers · this may take a while)",
                                 "ko": "📋 분기 재무제표 수집 중... ({n}개 · 시간이 걸릴 수 있습니다)"},
    "error.no_prices":          {"en": "Could not load price data.",
                                 "ko": "가격 데이터를 불러올 수 없습니다."},
    "error.short_period":       {"en": "Backtest period too short — not enough data.",
                                 "ko": "백테스트 기간이 짧아 분석 데이터가 부족합니다."},

    # Section headers (results screen)
    "sec.perf_compare": {"en": "📈 Performance Comparison", "ko": "📈 성과 지표 비교"},
    "sec.ic_core":      {"en": "📐 IC Core Metrics",        "ko": "📐 IC 핵심 지표"},
    "sec.turnover":     {"en": "🔄 Turnover Rate",           "ko": "🔄 턴오버율 (거래 회전율)"},
    "sec.ic_per_model": {"en": "🤖 IC by Model",             "ko": "🤖 모델별 IC 비교"},
    "sec.ic_trend":     {"en": "📈 IC Trend (Ensemble)",     "ko": "📈 IC 추이 (앙상블)"},
    "sec.ic_per_rebal": {"en": "📋 IC per Rebalance",        "ko": "📋 리밸런싱별 IC 상세"},
    "sec.picks_detail": {"en": "📋 Selected Stocks Detail",  "ko": "📋 선정 종목 상세 지표"},
    "sec.feat_top10":   {"en": "🏆 Top 10 Feature Importance","ko": "🏆 지표 중요도 TOP 10"},
    "sec.feat_per_model":{"en": "🤖 Feature Importance by Model (Top 15)",
                         "ko": "🤖 모델별 피처 중요도 비교 (TOP 15)"},

    # Metric labels
    "metric.cagr":       {"en": "CAGR",          "ko": "CAGR"},
    "metric.sharpe":     {"en": "Sharpe",        "ko": "Sharpe"},
    "metric.max_dd":     {"en": "Max DD",        "ko": "Max DD"},
    "metric.avg_to":     {"en": "Avg Turnover (per rebalance)",
                          "ko": "평균 턴오버 (1회)"},
    "metric.annual_to":  {"en": "Annual Turnover",
                          "ko": "연간 턴오버"},
    "metric.n_periods":  {"en": "Periods Analyzed",
                          "ko": "분석 기간 수"},
    "metric.n_periods_unit": {"en": "{n} runs", "ko": "{n}회"},
    "metric.avg_ic":     {"en": "{label} Avg IC", "ko": "{label} 평균 IC"},

    # Tab labels (results screen)
    "tab.performance":  {"en": "📈 Performance",       "ko": "📈 성과 비교"},
    "tab.ic":           {"en": "🎯 IC & Turnover",     "ko": "🎯 IC 분석 & 턴오버"},
    "tab.history":      {"en": "📋 Rebalance History", "ko": "📋 리밸런싱 히스토리"},
    "tab.importance":   {"en": "🔍 Feature Importance","ko": "🔍 지표 중요도"},
    "tab.heatmap":      {"en": "🗺️ Influence Heatmap", "ko": "🗺️ 영향력 히트맵"},
    "tab.tracking":     {"en": "📊 Tracking",          "ko": "📊 성과 추적"},
    "tab.live":         {"en": "🔴 AI Picks",          "ko": "🔴 AI 추천"},

    # Status / error messages
    "msg.short_period":   {"en": "Backtest period is too short — not enough performance data.",
                           "ko": "백테스트 기간이 짧아 성과 데이터가 부족합니다."},
    "msg.no_ic":          {"en": "Not enough IC data — try a longer backtest period.",
                           "ko": "IC 데이터가 부족합니다. 백테스트 기간을 늘려주세요."},
    "msg.no_history":     {"en": "No rebalance history available.",
                           "ko": "리밸런싱 히스토리가 없습니다."},
    "msg.no_importance":  {"en": "No feature importance data.",
                           "ko": "지표 중요도 데이터가 없습니다."},
    "msg.no_heatmap":     {"en": "No heatmap data.",
                           "ko": "히트맵 데이터가 없습니다."},
    "msg.run_first":      {"en": "Please run a backtest first.",
                           "ko": "백테스트를 먼저 실행하세요."},
    "msg.no_features":    {"en": "Cannot compute current features.",
                           "ko": "현재 지표 데이터를 계산할 수 없습니다."},
    "msg.no_model":       {"en": "No saved model. Re-run the backtest.",
                           "ko": "저장된 모델이 없습니다. 백테스트를 다시 실행해 주세요."},
    "msg.error_no_prices":{"en": "Could not load price data.",
                           "ko": "가격 데이터를 불러올 수 없습니다."},
    "msg.live_today":     {"en": "💡 Predicting using today's latest indicators.",
                           "ko": "💡 오늘 날짜 기준 최신 지표로 예측합니다."},
    "msg.live_date":      {"en": "💡 Predicting using indicators as of **{sel_date}**. Uses the last training model from the backtest.",
                           "ko": "💡 **{sel_date}** 기준 지표로 예측합니다. 예측 모델은 백테스트의 마지막 학습 모델을 사용합니다."},

    # Risk-free rate caption
    "caption.rf":         {"en": "Risk-free rate (3M T-bill avg over period): **{rf:.2%}**",
                           "ko": "무위험수익률 (T-bill 3M 기간평균): **{rf:.2%}**"},

    # Section headers — results
    "sec.perf_overall":   {"en": "📈 Overall Performance Summary",
                           "ko": "📈 전체 성과 요약"},
    "sec.real_returns":   {"en": "📊 Realized Returns per Rebalance",
                           "ko": "📊 리밸런싱 기간별 실제 수익률"},
    "sec.cumulative":     {"en": "📈 Strategy Cumulative Return",
                           "ko": "📈 추천 전략 누적 수익률 추이"},
    "sec.per_stock":      {"en": "🏆 Per-Stock Performance Stats",
                           "ko": "🏆 종목별 성과 통계"},
    "sec.rebal_log":      {"en": "📋 Detailed Rebalance Log",
                           "ko": "📋 리밸런싱 기간별 상세 기록"},
    "sec.ai_picks":       {"en": "🔴 AI Recommended Stocks",
                           "ko": "🔴 AI 추천 종목"},
    "sec.imp_per_model":  {"en": "📊 Group Weight Comparison by Model",
                           "ko": "📊 모델별 그룹 비중 비교"},
    "sec.imp_trend":      {"en": "📈 Top Indicator Importance Trend (Ensemble)",
                           "ko": "📈 앙상블 주요 지표 중요도 추이"},
    "sec.imp_stack":      {"en": "📊 Indicator Importance Share Trend (Stacked)",
                           "ko": "📊 지표 중요도 비중 추이 (누적 스택)"},
    "sec.imp_recent":     {"en": "📋 Recent Indicator Importance Ranking",
                           "ko": "📋 최근 지표 중요도 순위"},
    "sec.heat_timeline":  {"en": "🗺️ Indicator Influence Timeline Heatmap",
                           "ko": "🗺️ 지표 영향력 타임라인 히트맵"},
    "sec.heat_corr":      {"en": "🔗 Major Indicator Importance Correlation",
                           "ko": "🔗 주요 지표 중요도 상관관계"},
    "sec.live_importance":{"en": "🔑 Current AI Model Feature Importance (latest rebalance)",
                           "ko": "🔑 현재 AI 모델 지표 중요도 (최신 리밸런싱 기준)"},
    "sec.live_radar":     {"en": "🕸️ Top 5 Stocks Indicator Radar",
                           "ko": "🕸️ TOP 5 종목 지표 레이더"},

    # Expanders (educational)
    "exp.what_is_ic":     {"en": "📖 What is IC analysis?",
                           "ko": "📖 IC 분석이란?"},
    "exp.what_is_to":     {"en": "📖 What is turnover?",
                           "ko": "📖 턴오버율이란?"},
    "exp.model_doc":      {"en": "📖 About the model",
                           "ko": "📖 사용 모델 설명"},
    "exp.ai_model_doc":   {"en": "📖 AI model · consensus interpretation",
                           "ko": "📖 AI 모델 설명 · 합의도 해석"},

    # Misc UI strings
    "ui.show_n_features": {"en": "Number of features to show",
                           "ko": "표시할 지표 수"},
    "ui.spinner_features":{"en": "Computing latest indicators…",
                           "ko": "최신 지표 계산 중..."},
    "ui.ensemble_caption":{"en": "🤖 Ensemble prediction (Rank Average: RF + XGBoost + LightGBM)",
                           "ko": "🤖 앙상블 예측 (Rank Average: RF + XGBoost + LightGBM)"},
    "ui.single_caption":  {"en": "🤖 Single RF prediction",
                           "ko": "🤖 단일 RF 예측"},
    "ui.total_rebal":     {"en": "Total **{n}** rebalances completed",
                           "ko": "총 **{n}**회 리밸런싱 수행됨"},
    "ui.all_rank_caption":{"en": "**As of {date}, AI score ranking for all {n} analyzed stocks**",
                           "ko": "**{date} 기준 전체 분석 종목 AI 점수 순위 ({n}개)**"},
    "ui.warn_fetch_fail": {"en": "Failed to fetch {tier} ({url}): {e}",
                           "ko": "{tier} ({url}) 조회 실패: {e}"},
    "ui.warn_sp1500_fb":  {"en": "S&P 1500 list fetch failed. Using built-in list.",
                           "ko": "S&P 1500 목록 조회 실패. 내장 리스트 사용."},
}


# Merge into the global table at import time so tr("hero.title") works.
register_strings(_QUANT_LAB_STRINGS)
