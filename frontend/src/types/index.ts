// ============================================================
// Market Types
// ============================================================

export interface StockInfo {
  ticker: string;
  name: string;
  sector: string;
  industry: string;
  market_cap: number;
  exchange: string;
}

export interface HeatmapStock {
  ticker: string;
  name: string;
  market_cap: number;
  price: number;
  change_pct: number;
  volume: number;
}

export interface HeatmapSector {
  name: string;
  stocks: HeatmapStock[];
  total_market_cap?: number;
  avg_change_pct?: number;
}

export interface HeatmapResponse {
  sectors: HeatmapSector[];
  period: string;
  updated_at: string;
}

export interface ScreenerParams {
  sector?: string;
  industry?: string;
  min_cap?: number;
  max_cap?: number;
  min_pe?: number;
  max_pe?: number;
  min_pb?: number;
  max_pb?: number;
  min_dividend?: number;
  max_dividend?: number;
  sort_by?: string;
  sort_order?: "asc" | "desc";
  page?: number;
  page_size?: number;
}

export interface ScreenerResult {
  ticker: string;
  name: string;
  sector: string;
  industry: string;
  price: number;
  change_pct: number;
  market_cap: number;
  pe_ratio: number | null;
  pb_ratio: number | null;
  dividend_yield: number | null;
  volume: number;
  fifty_two_week_high: number;
  fifty_two_week_low: number;
}

export interface ScreenerResponse {
  results: ScreenerResult[];
  total: number;
  page: number;
  page_size: number;
}

export interface StockDetail {
  ticker: string;
  name: string;
  sector: string | null;
  industry: string | null;
  market_cap: number | null;
  exchange: string | null;
  description: string | null;
  employees: number | null;
  website: string | null;
  price: number | null;
  change_pct: number | null;
  prev_close: number | null;
  open: number | null;
  day_high: number | null;
  day_low: number | null;
  volume: number | null;
  avg_volume: number | null;
  pe_ratio: number | null;
  pb_ratio: number | null;
  ps_ratio: number | null;
  eps: number | null;
  roe: number | null;
  debt_to_equity: number | null;
  dividend_yield: number | null;
  beta: number | null;
  fifty_two_week_high: number | null;
  fifty_two_week_low: number | null;
}

export interface ChartDataPoint {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface CompareStock {
  ticker: string;
  name: string;
  price: number;
  change_pct: number;
  market_cap: number;
  pe_ratio: number | null;
  pb_ratio: number | null;
  dividend_yield: number | null;
  beta: number | null;
  roe: number | null;
  eps: number | null;
  chart_data: ChartDataPoint[];
}

export interface CompareResponse {
  stocks: CompareStock[];
  period: string;
}

export interface SearchResult {
  ticker: string;
  name: string;
  sector: string;
  exchange: string;
}

export interface IndexInfo {
  ticker: string;
  name: string;
  price: number;
  change: number;
  change_pct: number;
}

// ============================================================
// Portfolio Types
// ============================================================

export interface Portfolio {
  id: number;
  name: string;
  description: string;
  created_at: string;
  total_value: number | null;
  total_cost: number | null;
  total_gain: number | null;
  total_gain_pct: number | null;
  total_unrealized_gain: number | null;
  total_unrealized_gain_pct: number | null;
  realized_gain: number | null;
  holdings?: Holding[];
}

export interface Holding {
  ticker: string;
  name: string;
  sector: string;
  quantity: number;
  avg_cost: number;
  current_price: number;
  market_value: number;
  total_cost: number;
  unrealized_gain: number;
  unrealized_gain_pct: number | null;
}

export interface Trade {
  id: number;
  portfolio_id: number;
  ticker: string;
  trade_type: "BUY" | "SELL";
  quantity: number;
  price: number;
  commission: number;
  trade_date: string;
  note: string | null;
  created_at: string;
}

export interface TradeCreate {
  ticker: string;
  trade_type: "BUY" | "SELL";
  quantity: number;
  price: number;
  commission?: number;
  trade_date: string;
  note?: string;
}

export interface AllocationItem {
  label: string;
  value: number;
  percentage: number;
  color: string;
}

export interface AllocationResponse {
  by_stock: AllocationItem[];
  by_sector: AllocationItem[];
  total_value: number;
}

export interface PerformancePoint {
  date: string;
  portfolio_value: number;
  total_cost: number;
  gain_pct: number;
  spy_pct: number | null;
  qqq_pct: number | null;
}

export interface PerformanceResponse {
  points: PerformancePoint[];
  total_return_pct: number;
  spy_return_pct: number | null;
  qqq_return_pct: number | null;
}

export interface DividendEvent {
  ticker: string;
  name: string;
  ex_date: string;
  payment_date: string | null;
  amount: number;
  quantity: number;
  total_amount: number;
}

export interface DividendSummary {
  events: DividendEvent[];
  total_annual: number;
  monthly_breakdown: Record<string, number>;
}

export interface TaxSummary {
  year: number;
  realized_gains: number;
  realized_losses: number;
  net_gain: number;
  short_term_gain: number;
  long_term_gain: number;
  short_term_loss: number;
  long_term_loss: number;
  trades: Trade[];
}

// ============================================================
// Sentiment Types
// ============================================================

export interface NewsArticle {
  id: number;
  ticker: string | null;
  headline: string;
  summary: string;
  source: string;
  url: string;
  published_at: string;
  sentiment: number;
  sentiment_label: string;
  ai_summary: string | null;
}

export interface NewsResponse {
  articles: NewsArticle[];
  total: number;
  page: number;
  page_size: number;
}

export interface FearGreedData {
  score: number;
  label: string;
  vix_score: number | null;
  momentum_score: number | null;
  put_call_score: number | null;
  high_low_score: number | null;
  volume_score: number | null;
  updated_at: string;
}

export type FearGreedHistory = FearGreedData[];

export interface SentimentTrendPoint {
  date: string;
  avg_sentiment: number;
  article_count: number;
}

export interface SentimentTrend {
  ticker: string;
  trend: SentimentTrendPoint[];
}

export interface DailyReport {
  date: string;
  content: string;
  generated_at: string;
}

// ============================================================
// Common Types
// ============================================================

export type Period = "1d" | "1w" | "1m" | "3m" | "6m" | "ytd" | "1y" | "5y";
export type ChartInterval = "1m" | "5m" | "15m" | "1h" | "1d" | "1wk" | "1mo";
export type SentimentLabel =
  | "Very Bullish"
  | "Bullish"
  | "Neutral"
  | "Bearish"
  | "Very Bearish";
