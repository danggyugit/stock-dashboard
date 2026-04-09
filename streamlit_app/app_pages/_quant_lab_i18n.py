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

    # Progress messages while running a backtest
    "prog.surv_load":         {"en": "📜 Loading S&P 500 change history (survivorship bias fix)…",
                               "ko": "📜 S&P 500 변경 이력 로드 중 (생존자 편향 보정)..."},
    "prog.dl_prices":         {"en": "📡 Downloading price data for {n} tickers…",
                               "ko": "📡 {n}개 종목 가격 데이터 다운로드 중..."},
    "prog.prices_done":       {"en": "✅ {n} tickers loaded ({extra} historical delisted included). Loading fundamentals…",
                               "ko": "✅ {n}개 종목 ({extra}개 역사적 퇴출 종목 포함). 펀더멘털 로드 중..."},
    "prog.fund_done":         {"en": "✅ Fundamentals: {ok}/{n}. Loading PIT quarterly statements…",
                               "ko": "✅ 펀더멘털 완료: {ok}/{n}개. PIT 분기 재무제표 수집 중..."},
    "prog.pit_loading":       {"en": "📋 Collecting quarterly statements ({n} tickers · this may take a while)",
                               "ko": "📋 분기 재무제표 수집 중... ({n}개 · 시간이 걸릴 수 있습니다)"},
    "prog.pit_done":          {"en": "✅ PIT statements: {ok}/{n}. Computing technical indicators…",
                               "ko": "✅ PIT 재무제표 완료: {ok}/{n}개. 기술지표 계산 중..."},
    "prog.tech_loading":      {"en": "📡 Downloading SPY · VIX + computing technical indicators…",
                               "ko": "📡 SPY·VIX 다운로드 + 기술지표 계산 중..."},
    "prog.tech_done":         {"en": "📈 Technical indicators ready ({n} tickers). Starting backtest…",
                               "ko": "📈 기술지표 계산 완료 ({n}종목). 백테스트 시작..."},
    "prog.training":          {"en": "🤖 Training AI model and running backtest…",
                               "ko": "🤖 AI 모델 학습 및 백테스트 실행 중..."},
    "prog.complete":          {"en": "✅ Backtest complete! {rebal} rebalances | {trains} trainings | {n} tickers analyzed",
                               "ko": "✅ 백테스트 완료! {rebal}회 리밸런싱 | {trains}회 학습 | {n}개 종목 분석"},
    "prog.snapshot":          {"en": "Computing snapshots ({i}/{total})…",
                               "ko": "스냅샷 계산 중 ({i}/{total})..."},
    "prog.done_short":        {"en": "✅ Done!",
                               "ko": "✅ 완료!"},
    "prog.short_period":      {"en": "Backtest period too short — not enough analytics data.",
                               "ko": "백테스트 기간이 짧아 분석 데이터가 부족합니다."},

    # Result chart axes / titles
    "ax.cumulative_compare":  {"en": "Portfolio Cumulative Return Comparison",
                               "ko": "포트폴리오 누적 수익률 비교"},
    "ax.date":                {"en": "Date",            "ko": "날짜"},
    "ax.cum_return":          {"en": "Cumulative Return (1.0 = start)",
                               "ko": "누적 수익 (1.0 = 시작)"},
    "ax.return_pct":          {"en": "Return (%)",      "ko": "수익률"},
    "ax.rebalance_date":      {"en": "Rebalance Date",  "ko": "리밸런싱 날짜"},
    "ax.importance":          {"en": "Importance",      "ko": "중요도"},
    "ax.indicator":           {"en": "Indicator",       "ko": "지표"},
    "ax.ticker":              {"en": "Ticker",          "ko": "티커"},
    "ax.ai_score":            {"en": "AI Score",        "ko": "AI 점수"},
    "ax.rank":                {"en": "Rank",            "ko": "순위"},
    "ax.ai_strategy":         {"en": "AI Strategy",     "ko": "AI 전략"},

    # IC labels
    "ic.mean":                {"en": "Mean IC",          "ko": "평균 IC"},
    "ic.std":                 {"en": "IC Std Dev",       "ko": "IC 표준편차"},
    "ic.ir":                  {"en": "IC IR",            "ko": "IC IR"},
    "ic.pos_rate":            {"en": "Positive IC Ratio","ko": "양(+)IC 비율"},

    # Rebalance history
    "rh.select":              {"en": "Select rebalance period",
                               "ko": "리밸런싱 기간 선택"},
    "rh.rebal_date":          {"en": "Rebalance Date",  "ko": "리밸런싱 기준일"},
    "rh.holding_period":      {"en": "Holding Period",  "ko": "보유 기간"},
    "rh.learn_period":        {"en": "Training Window", "ko": "주가 학습 기간"},
    "rh.period_return":       {"en": "Period Return",   "ko": "기간 수익률"},

    # Tracking summary
    "tk.win_rate":            {"en": "Rebalance Win Rate", "ko": "리밸런싱 승률"},
    "tk.avg_return":          {"en": "Avg Period Return",  "ko": "기간 평균 수익"},
    "tk.cumulative":          {"en": "Cumulative Return",  "ko": "누적 수익률"},
    "tk.best":                {"en": "Best Period",        "ko": "최고 수익 기간"},
    "tk.worst":               {"en": "Worst Period",       "ko": "최저 수익 기간"},

    # AI Picks
    "pk.as_of":               {"en": "As-of date",        "ko": "분석 기준일"},
    "pk.consensus":           {"en": "Consensus",         "ko": "합의도"},
    "pk.recommend":           {"en": "Pick",              "ko": "추천"},
    "pk.title":               {"en": "AI Recommendation Score ({date})",
                               "ko": "AI 추천 종목 점수 ({date})"},

    # More chart titles + axes used in result tabs
    "chart.turnover_per_rebal": {"en": "Turnover per Rebalance",
                                 "ko": "리밸런싱별 턴오버율"},
    "chart.ic_per_model":       {"en": "IC per Model per Rebalance",
                                 "ko": "리밸런싱별 모델 IC 비교"},
    "chart.cum_ic_per_model":   {"en": "Cumulative IC by Model",
                                 "ko": "누적 IC 비교 (모델별)"},
    "chart.ic_per_rebal":       {"en": "IC per Rebalance",
                                 "ko": "리밸런싱별 IC"},
    "chart.cum_ic":             {"en": "Cumulative IC",
                                 "ko": "누적 IC"},
    "chart.ic_dist":            {"en": "IC Distribution",
                                 "ko": "IC 분포 히스토그램"},
    "chart.norm_importance":    {"en": "Normalized Importance (share)",
                                 "ko": "정규화 중요도 (비중)"},
    "chart.corr":               {"en": "Correlation",
                                 "ko": "상관계수"},
    "chart.top20_avg_return":   {"en": "Top 20 Stocks by Avg Return",
                                 "ko": "종목별 평균 수익률 TOP 20"},
    "chart.current_top15_imp":  {"en": "Current Top 15 Indicator Importance",
                                 "ko": "현재 지표 중요도 TOP 15"},
    "chart.short_period_msg":   {"en": "Try switching to auto date or moving the start date earlier.",
                                 "ko": "날짜를 자동 설정으로 변경하거나 시작일을 앞당겨 주세요."},
    # Long-form explainer body for the Turnover expander
    "exp.what_is_to_body": {
        "en": (
            "| Metric | Definition | Threshold |\n"
            "|--------|------------|-----------|\n"
            "| **Avg Turnover** | Share of holdings replaced per rebalance | "
            "lower = friendlier on transaction cost |\n"
            "| **Annual Turnover** | Avg turnover × rebalances per year | "
            "1.0 = full portfolio replaced once a year |\n\n"
            "- 50% turnover means half of the holdings are swapped each rebalance.\n"
            "- Higher annual turnover translates directly into higher trading-cost drag."
        ),
        "ko": (
            "| 지표 | 정의 | 기준 |\n"
            "|------|------|------|\n"
            "| **평균 턴오버** | 리밸런싱 1회당 교체되는 종목 비율 | 낮을수록 거래비용 유리 |\n"
            "| **연간 턴오버** | 평균 턴오버 × 연간 리밸런싱 횟수 | 1.0 = 포트폴리오 1회 완전 교체 |\n\n"
            "- 턴오버 50% = 리밸런싱마다 절반의 종목이 교체됨\n"
            "- 연간 턴오버가 높을수록 실제 거래비용 부담이 커짐"
        ),
    },

    # Long-form explainer body for the model documentation expander
    "exp.model_doc_body": {
        "en": (
            "| Model | What it does | Strengths | Weaknesses |\n"
            "|-------|--------------|-----------|------------|\n"
            "| **Random Forest (RF)** | Average of many decision trees, each "
            "trained on a random subset of data and features. | Robust to "
            "overfitting, stable on outliers, easy to interpret | Weaker at "
            "capturing non-linear patterns vs boosting |\n"
            "| **XGBoost (XGB)** | Gradient boosting where each new tree "
            "corrects the previous tree's error. | High accuracy, captures "
            "complex patterns, built-in regularization | Risk of overfitting, "
            "sensitive to hyperparameters |\n"
            "| **LightGBM (LGBM)** | Like XGBoost but uses leaf-wise splitting "
            "for faster, more memory-efficient training. | Optimized for large "
            "datasets, native categorical features, fast training | Can "
            "overfit on small datasets |\n\n"
            "**Ensemble effect**: each model interprets the data differently, "
            "so when one is wrong the others compensate. RF gives a stable "
            "baseline; XGBoost and LightGBM capture the finer-grained patterns."
        ),
        "ko": (
            "| 모델 | 특징 | 강점 | 약점 |\n"
            "|------|------|------|------|\n"
            "| **Random Forest (RF)** | 여러 결정 트리의 평균 예측. 각 트리는 "
            "랜덤 데이터·피처 조합으로 학습. | 과적합에 강건, 이상치에 안정적, "
            "해석 용이 | 비선형 패턴 포착력이 부스팅 대비 약함 |\n"
            "| **XGBoost (XGB)** | 이전 트리의 오차를 다음 트리가 보정하는 "
            "그래디언트 부스팅. | 높은 예측 정확도, 복잡한 패턴 학습, 정규화 내장 | "
            "과적합 위험, 하이퍼파라미터 민감 |\n"
            "| **LightGBM (LGBM)** | XGBoost와 유사하나 리프 기반 분할로 더 빠르고 "
            "메모리 효율적. | 대규모 데이터에 최적, 범주형 피처 지원, 학습 속도 | "
            "소규모 데이터에서 과적합 가능 |\n\n"
            "**앙상블 효과**: 3모델이 서로 다른 방식으로 데이터를 해석하므로, 한 "
            "모델이 틀려도 나머지가 보완합니다. RF는 안정적 기반을 제공하고, "
            "XGBoost/LightGBM은 세밀한 패턴을 포착합니다."
        ),
    },

    # Long-form explainer body for the AI Picks expander
    "exp.ai_model_doc_body": {
        "en": (
            "| Model | Role |\n"
            "|-------|------|\n"
            "| **Random Forest** | Stable foundation. Average of many decision "
            "trees, robust to overfitting. |\n"
            "| **XGBoost** | Captures fine-grained patterns by repeatedly "
            "correcting previous-tree errors. |\n"
            "| **LightGBM** | Fast training optimized for large datasets via "
            "leaf-wise splitting. |\n\n"
            "**Consensus (★)**\n"
            "- ★★★ : picked by all 3 models → **highest confidence**\n"
            "- ★★ : picked by 2 models → strong candidate\n"
            "- ★ : picked by 1 model only → idiosyncratic call, double-check\n"
            "- (blank) : not recommended\n\n"
            "**How to use it**: prioritize ★★★ names; only act on ★ names "
            "after additional verification."
        ),
        "ko": (
            "| 모델 | 역할 |\n"
            "|------|------|\n"
            "| **Random Forest** | 안정적 기반. 여러 결정 트리의 평균으로 과적합에 강건. |\n"
            "| **XGBoost** | 세밀한 패턴 포착. 이전 트리의 오차를 반복 보정. |\n"
            "| **LightGBM** | 빠른 학습 + 대규모 데이터 최적화. 리프 기반 분할. |\n\n"
            "**합의도 (★)**\n"
            "- ★★★ : 3모델 모두 TOP N에 선정 → **가장 신뢰도 높음**\n"
            "- ★★ : 2모델이 TOP N에 선정 → 유력 후보\n"
            "- ★ : 1모델만 선정 → 특정 모델의 독자적 판단, 주의 필요\n"
            "- (빈칸) : 추천 대상 아님\n\n"
            "**활용법**: ★★★ 종목을 우선 검토하고, ★ 종목은 추가 확인 후 결정하세요."
        ),
    },

    # Long-form explainer body for the IC expander
    "exp.what_is_ic_body": {
        "en": (
            "**IC (Information Coefficient)** is the key metric for evaluating "
            "an AI model's predictive power.\n\n"
            "| Metric | Definition | Threshold |\n"
            "|--------|------------|-----------|\n"
            "| **IC** | Spearman correlation between predicted-return rank and "
            "actual-return rank | > 0.05 = good, > 0 = useful |\n"
            "| **IC IR** | Mean IC ÷ Std IC (consistency of prediction) | "
            "> 0.5 = excellent, > 0.3 = solid |\n"
            "| **Positive IC ratio** | Share of rebalances with IC > 0 | "
            "> 60% = stable |\n\n"
            "**How to read it**\n"
            "- Consistently **positive IC** means the AI is reliably picking "
            "winners.\n"
            "- IC ≈ 0 means no predictive signal; IC < 0 means inverse "
            "prediction (warning sign).\n"
            "- An **upward-sloping cumulative IC** indicates model quality is "
            "holding up over time.\n"
            "- Academically, **IC > 0.05** is considered practically "
            "meaningful predictive power."
        ),
        "ko": (
            "**IC (Information Coefficient, 정보 계수)**는 AI 모델의 예측력을 "
            "평가하는 핵심 지표입니다.\n\n"
            "| 지표 | 정의 | 기준 |\n"
            "|------|------|------|\n"
            "| **IC** | AI 예측 수익률 순위와 실제 수익률 순위 간의 "
            "**Spearman 상관계수** | > 0.05 = 좋음, > 0 = 유효 |\n"
            "| **IC IR** | IC 평균 ÷ IC 표준편차 (예측 일관성) | "
            "> 0.5 = 우수, > 0.3 = 양호 |\n"
            "| **양(+)IC 비율** | IC > 0인 리밸런싱 기간 비율 | > 60% = 안정적 |\n\n"
            "**해석 방법**\n"
            "- IC가 꾸준히 **양수(+)**이면 AI 모델이 상승 종목을 잘 예측함을 "
            "의미합니다.\n"
            "- IC = 0이면 예측력 없음, IC < 0이면 역방향 예측 (위험 신호).\n"
            "- 누적 IC가 **우상향** 추세이면 모델 품질이 일관적으로 유지되고 있습니다.\n"
            "- 학술적으로 IC > 0.05이면 실용적으로 유의미한 예측력으로 간주합니다."
        ),
    },
    "chart.short_period_full":  {
        "en": ("Backtest period is too short. Need at least {n_needed} rebalance "
               "dates (currently {n_have}). Training {rolling}× + testing {min_test}× "
               "+ 1y indicator warm-up ≈ {months} months minimum. "
               "Try switching to auto date or moving the start date earlier."),
        "ko": ("백테스트 기간이 부족합니다. 최소 {n_needed}개 리밸런싱 날짜 필요 "
               "(현재 {n_have}개). 학습 {rolling}회 + 테스트 {min_test}회 + 지표 "
               "warm-up 1년 = 약 {months}개월 이상의 기간이 필요합니다. "
               "날짜를 자동 설정으로 변경하거나 시작일을 앞당겨 주세요."),
    },

    # ── Ver4.2: New settings strings ──────────────────────
    "settings.turnover_buffer":      {"en": "Turnover buffer (prefer existing holdings)",
                                      "ko": "턴오버 버퍼 (보유 종목 우선)"},
    "settings.turnover_buffer_help": {
        "en": ("Gives a 5% bonus score to existing holdings. "
               "Keeps stocks that slip slightly in rank, reducing unnecessary trades. "
               "Effect: 30-50% turnover reduction → lower transaction costs, less noise trading."),
        "ko": ("이미 보유 중인 종목에 5% 가산점을 부여합니다. "
               "순위가 약간 밀려도 기존 보유 종목을 유지하여 불필요한 매매를 줄입니다. "
               "효과: 턴오버 30~50% 감소 → 거래비용 절약, 노이즈성 교체 방지."),
    },
    "settings.mom_filter":      {"en": "Momentum filter (exclude falling stocks)",
                                 "ko": "모멘텀 필터 (하락 종목 제외)"},
    "settings.mom_filter_help": {
        "en": ("Excludes stocks with negative 1-month return from recommendations. "
               "Even if AI score is high, stocks in a downtrend are filtered out. "
               "Effect: avoids falling stocks → improves excess return & Profit Factor."),
        "ko": ("최근 1개월 수익률이 마이너스인 종목을 추천 후보에서 제외합니다. "
               "AI 점수가 높아도 현재 하락 추세인 종목은 선정하지 않습니다. "
               "효과: 하락 종목 회피 → 선정 초과수익·Profit Factor 개선."),
    },
    "settings.inv_vol":      {"en": "Inverse volatility weighting (Risk-Parity)",
                              "ko": "역변동성 가중 (Risk-Parity)"},
    "settings.inv_vol_help": {
        "en": ("Allocates more weight to lower-volatility stocks. "
               "E.g., 15% vol → 28% weight, 50% vol → 11% weight. "
               "Effect: lower MDD, higher Sharpe. But may reduce gains from volatile winners. "
               "Shows per-stock weight (%) in the Picks tab."),
        "ko": ("변동성이 낮은 종목에 더 많은 비중을 배분합니다. "
               "예: 변동성 15% 종목에 28%, 변동성 50% 종목에 11%. "
               "효과: MDD 축소, Sharpe 개선. 단, 고변동 종목의 급등 수익은 줄어들 수 있습니다. "
               "추천 탭에서 종목별 투자 비중(%)을 함께 표시합니다."),
    },

    # ── Ver4.2: Summary tab strings ───────────────────────
    "tab.summary":          {"en": "🏠 Summary",        "ko": "🏠 요약"},
    "sum.sec_perf":         {"en": "🏆 Key Performance Summary",
                             "ko": "🏆 핵심 성과 요약"},
    "sum.total_return":     {"en": "Total Return",      "ko": "총수익률"},
    "sum.win_rate":         {"en": "Monthly Win Rate",   "ko": "월승률"},
    "sum.diff":             {"en": "Diff",               "ko": "차이"},
    "sum.metrics_compare":  {"en": "📊 Metrics Comparison",
                             "ko": "📊 성과 지표 비교"},
    "sum.sec_ic":           {"en": "🎯 IC & Model Predictive Power",
                             "ko": "🎯 IC & 모델 예측력"},
    "sum.sec_quality":      {"en": "🎯 Stock Selection Quality",
                             "ko": "🎯 종목 선정 품질"},
    "sum.excess_return":    {"en": "Selection Excess Return<br>(Top N − Universe Avg)",
                             "ko": "선정 초과수익<br>(Top N - 유니버스 평균)"},
    "sum.long_short":       {"en": "Long-Short Spread<br>(Top N − Bottom N)",
                             "ko": "롱숏 스프레드<br>(Top N - Bottom N)"},
    "sum.precision":        {"en": "Hit Rate<br>(Above-Avg Ratio)",
                             "ko": "적중률<br>(평균 초과 종목 비율)"},
    "sum.profit_factor":    {"en": "Profit Factor<br>(Gain / Loss)",
                             "ko": "Profit Factor<br>(총이익 / 총손실)"},
    "sum.avg":              {"en": "Avg",                "ko": "평균"},
    "sum.chart_excess":     {"en": "Top N vs Universe Avg (Excess Return)",
                             "ko": "Top N vs 유니버스 평균 (초과수익)"},
    "sum.chart_longshort":  {"en": "Long-Short Spread (Top N − Bottom N)",
                             "ko": "롱숏 스프레드 (Top N - Bottom N)"},
    "sum.sec_trade":        {"en": "🔄 Trade Efficiency & Win Rate",
                             "ko": "🔄 거래 효율 & 승률"},
    "sum.n_rebal":          {"en": "Rebalance Count",    "ko": "리밸런싱 횟수"},
    "sum.unit_times":       {"en": " runs",              "ko": "회"},
    "sum.sec_recent":       {"en": "📋 Latest Rebalance",
                             "ko": "📋 최근 리밸런싱"},

    # ── Ver4.2: Advanced settings section labels ──────────
    "settings.adv_data_quality": {"en": "Data Quality",
                                  "ko": "데이터 품질"},
    "settings.adv_strategy":     {"en": "Strategy Options",
                                  "ko": "전략 옵션"},
    "settings.vol_no_filter":    {"en": "$0 (No filter)",
                                  "ko": "$0 (필터 없음)"},
    "settings.select_all_sectors": {"en": "Select all sectors",
                                    "ko": "전체 섹터 선택"},
    "settings.form_date_hint":  {"en": "💡 Dates auto-adjust based on rolling window & rebalance period at run time.",
                                 "ko": "💡 날짜는 실행 시 롤링 윈도우·리밸런싱 기간에 맞춰 자동 조정됩니다."},
}


# Merge into the global table at import time so tr("hero.title") works.
register_strings(_QUANT_LAB_STRINGS)
