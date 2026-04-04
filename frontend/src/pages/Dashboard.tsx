import { useMemo, useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { useQuery, useQueries } from "@tanstack/react-query";
import { ArrowRight, Check, ChevronsUpDown } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  AreaChart,
  Area,
  ResponsiveContainer,
  YAxis,
} from "recharts";
import Heatmap from "@/components/market/Heatmap";
import AllocationChart from "@/components/portfolio/AllocationChart";
import PerformanceChart from "@/components/portfolio/PerformanceChart";
import { getIndices, getHeatmapData, getChartData } from "@/api/market";
import { getPortfolios, getPortfolioDetail, getPerformance } from "@/api/portfolio";
import { getNews } from "@/api/sentiment";
import { formatCurrency, formatDate } from "@/lib/utils";
import type {
  IndexInfo,
  HeatmapResponse,
  ChartDataPoint,
  Portfolio,
  Holding,
  PerformanceResponse,
  AllocationResponse,
  NewsArticle,
} from "@/types";

const INDEX_TICKERS = [
  { ticker: "^DJI", label: "DOW", period: "1d" as const, interval: "5m" as const },
  { ticker: "^IXIC", label: "NASDAQ", period: "1d" as const, interval: "5m" as const },
  { ticker: "^GSPC", label: "S&P 500", period: "1d" as const, interval: "5m" as const },
  { ticker: "^VIX", label: "VIX", period: "1m" as const, interval: "1d" as const },
];

const ALLOC_COLORS = [
  "#3B82F6", "#EF4444", "#10B981", "#F59E0B", "#8B5CF6",
  "#EC4899", "#06B6D4", "#F97316", "#14B8A6", "#6366F1",
];

/* ─── Mini Index Card ─── */
const MiniIndexCard = ({
  def,
  indexInfo,
}: {
  def: (typeof INDEX_TICKERS)[number];
  indexInfo?: IndexInfo;
}) => {
  const { data: chartData, isLoading } = useQuery<ChartDataPoint[]>({
    queryKey: ["indexChart", def.ticker],
    queryFn: () => getChartData(def.ticker, def.period, def.interval),
    staleTime: 5 * 60_000,
  });

  const price = indexInfo?.price;
  const change = indexInfo?.change;
  const changePct = indexInfo?.change_pct;
  const isUp = (changePct ?? 0) >= 0;
  const color = isUp ? "#22c55e" : "#ef4444";

  return (
    <Card className="overflow-hidden">
      <CardContent className="p-2.5">
        <div className="flex items-center justify-between mb-0.5">
          <div className="flex items-center gap-1">
            <span className="font-bold text-xs">{def.label}</span>
            {def.interval === "1d" && (
              <span className="text-[9px] text-muted-foreground bg-muted px-1 rounded">1M Daily</span>
            )}
          </div>
          {changePct != null && (
            <span className={`text-[11px] font-semibold ${isUp ? "text-green-500" : "text-red-500"}`}>
              {changePct >= 0 ? "+" : ""}{changePct.toFixed(2)}%
            </span>
          )}
        </div>
        <div className="flex items-baseline gap-1.5">
          <span className="text-base font-bold tabular-nums">
            {price != null ? price.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "--"}
          </span>
          {change != null && (
            <span className={`text-[10px] ${isUp ? "text-green-500" : "text-red-500"}`}>
              {change >= 0 ? "+" : ""}{change.toFixed(2)}
            </span>
          )}
        </div>
        <div className="h-14 -mx-1">
          {isLoading ? (
            <Skeleton className="w-full h-full" />
          ) : chartData && chartData.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 2, right: 0, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id={`grad-${def.ticker}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={color} stopOpacity={0.3} />
                    <stop offset="95%" stopColor={color} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <YAxis domain={["dataMin", "dataMax"]} hide />
                <Area
                  type="monotone"
                  dataKey="close"
                  stroke={color}
                  fill={`url(#grad-${def.ticker})`}
                  strokeWidth={1.5}
                  dot={false}
                  isAnimationActive={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-full text-[10px] text-muted-foreground">
              No chart
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
};

/* ─── Gain Bar (colored percentage bar) ─── */
const GainBar = ({ pct }: { pct: number | null }) => {
  if (pct == null) return <span className="text-muted-foreground text-xs">--</span>;
  const isUp = pct >= 0;
  const width = Math.min(Math.abs(pct) * 2, 100);
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${isUp ? "bg-green-500" : "bg-red-500"}`}
          style={{ width: `${width}%` }}
        />
      </div>
      <span className={`text-xs font-semibold tabular-nums w-14 text-right ${isUp ? "text-green-600" : "text-red-600"}`}>
        {pct >= 0 ? "+" : ""}{pct.toFixed(1)}%
      </span>
    </div>
  );
};

/* ─── Dashboard Page ─── */
const Dashboard = () => {
  const { data: indices } = useQuery<IndexInfo[]>({
    queryKey: ["indices"],
    queryFn: getIndices,
    staleTime: 60_000,
  });

  const { data: heatmapData, isLoading: heatmapLoading } =
    useQuery<HeatmapResponse>({
      queryKey: ["heatmap", "1d"],
      queryFn: () => getHeatmapData("1d"),
      staleTime: 5 * 60_000,
    });

  const { data: portfolios } = useQuery<Portfolio[]>({
    queryKey: ["portfolios"],
    queryFn: getPortfolios,
    staleTime: 60_000,
  });

  // Multi-select portfolio state
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [selectorOpen, setSelectorOpen] = useState(false);

  // Auto-select all portfolios on first load
  useEffect(() => {
    if (portfolios && portfolios.length > 0 && selectedIds.length === 0) {
      setSelectedIds(portfolios.map((p) => p.id));
    }
  }, [portfolios, selectedIds.length]);

  const allSelected = portfolios ? selectedIds.length === portfolios.length : false;

  const toggleId = (id: number) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  };
  const toggleAll = () => {
    if (!portfolios) return;
    setSelectedIds(allSelected ? [] : portfolios.map((p) => p.id));
  };

  // Fetch detail for each selected portfolio
  const detailQueries = useQueries({
    queries: selectedIds.map((id) => ({
      queryKey: ["portfolioDetail", id],
      queryFn: () => getPortfolioDetail(id),
      staleTime: 60_000,
      enabled: true,
    })),
  });

  // First selected portfolio for performance chart
  const firstSelectedId = selectedIds[0] ?? null;
  const { data: performance, isLoading: perfLoading } = useQuery<PerformanceResponse>({
    queryKey: ["performance", firstSelectedId, "3m"],
    queryFn: () => getPerformance(firstSelectedId!, "3m"),
    enabled: firstSelectedId !== null,
    staleTime: 60_000,
  });

  const indexMap = new Map<string, IndexInfo>();
  indices?.forEach((idx) => indexMap.set(idx.ticker, idx));

  // Merge holdings from all selected portfolios
  const allPortfolioDetails = detailQueries
    .map((q) => q.data)
    .filter(Boolean) as Portfolio[];

  const mergedHoldings = useMemo(() => {
    const holdingMap = new Map<string, Holding>();
    for (const p of allPortfolioDetails) {
      for (const h of p.holdings ?? []) {
        const existing = holdingMap.get(h.ticker);
        if (existing) {
          const totalQty = existing.quantity + h.quantity;
          const totalCost = (existing.quantity * existing.avg_cost) + (h.quantity * h.avg_cost);
          const totalMv = (existing.market_value ?? 0) + (h.market_value ?? 0);
          const totalUg = (existing.unrealized_gain ?? 0) + (h.unrealized_gain ?? 0);
          holdingMap.set(h.ticker, {
            ...existing,
            quantity: totalQty,
            avg_cost: totalQty > 0 ? totalCost / totalQty : 0,
            market_value: totalMv,
            total_cost: (existing.total_cost ?? 0) + (h.total_cost ?? 0),
            unrealized_gain: totalUg,
            unrealized_gain_pct: totalCost > 0 ? (totalUg / totalCost) * 100 : null,
          });
        } else {
          holdingMap.set(h.ticker, { ...h });
        }
      }
    }
    return [...holdingMap.values()].sort(
      (a, b) => (b.market_value ?? 0) - (a.market_value ?? 0),
    );
  }, [allPortfolioDetails]);

  const holdings = mergedHoldings;
  const totalValue = allPortfolioDetails.reduce((s, p) => s + (p.total_value ?? 0), 0);
  const totalCost = allPortfolioDetails.reduce((s, p) => s + (p.total_cost ?? 0), 0);
  const totalGain = totalValue - totalCost;
  const totalGainPct = totalCost > 0 ? (totalGain / totalCost) * 100 : null;

  // Fetch news for all holdings tickers
  const holdingTickers = holdings.map((h) => h.ticker);
  const newsQuery = useQuery<NewsArticle[]>({
    queryKey: ["holdingsNews", holdingTickers.join(",")],
    queryFn: async () => {
      if (holdingTickers.length === 0) return [];
      const results: NewsArticle[] = [];
      const seen = new Set<string>();
      const responses = await Promise.allSettled(
        holdingTickers.map((t) => getNews(t, 1, 5)),
      );
      for (const resp of responses) {
        if (resp.status === "fulfilled" && resp.value.articles) {
          for (const a of resp.value.articles) {
            if (!seen.has(a.headline)) {
              seen.add(a.headline);
              results.push(a);
            }
          }
        }
      }
      results.sort((a, b) => (b.published_at ?? "").localeCompare(a.published_at ?? ""));
      return results.slice(0, 15);
    },
    enabled: holdingTickers.length > 0,
    staleTime: 5 * 60_000,
  });
  const holdingsNews = newsQuery.data ?? [];

  // Compute allocation from merged holdings
  const allocation = useMemo((): AllocationResponse | null => {
    if (!holdings.length) return null;
    const tv = holdings.reduce((s, h) => s + (h.market_value ?? h.quantity * h.avg_cost), 0);
    if (tv === 0) return null;
    const byStock = holdings.map((h, i) => {
      const val = h.market_value ?? h.quantity * h.avg_cost;
      return {
        label: h.ticker,
        value: Math.round(val * 100) / 100,
        percentage: Math.round((val / tv) * 10000) / 100,
        color: ALLOC_COLORS[i % ALLOC_COLORS.length],
      };
    });
    const sectorMap = new Map<string, number>();
    holdings.forEach((h) => {
      const s = h.sector || "Unknown";
      const val = h.market_value ?? h.quantity * h.avg_cost;
      sectorMap.set(s, (sectorMap.get(s) || 0) + val);
    });
    const bySector = [...sectorMap.entries()]
      .sort((a, b) => b[1] - a[1])
      .map(([label, value], i) => ({
        label,
        value: Math.round(value * 100) / 100,
        percentage: Math.round((value / tv) * 10000) / 100,
        color: ALLOC_COLORS[i % ALLOC_COLORS.length],
      }));
    return { by_stock: byStock, by_sector: bySector, total_value: tv };
  }, [holdings]);

  return (
    <div className="space-y-3">
      {/* ── Index Mini Charts ── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
        {INDEX_TICKERS.map((def) => (
          <MiniIndexCard key={def.ticker} def={def} indexInfo={indexMap.get(def.ticker)} />
        ))}
      </div>

      {/* ── Market Heatmap ── */}
      <section>
        <div className="flex items-center justify-between mb-1">
          <h2 className="text-sm font-semibold">Market Heatmap</h2>
          <Link to="/market">
            <Button variant="ghost" size="sm" className="h-7 text-xs">
              View Market <ArrowRight className="ml-1 h-3 w-3" />
            </Button>
          </Link>
        </div>
        <Card>
          <CardContent className="p-1">
            <div className="h-[600px]">
              {heatmapLoading ? (
                <Skeleton className="w-full h-full" />
              ) : heatmapData && heatmapData.sectors.length > 0 ? (
                <Heatmap data={heatmapData} />
              ) : (
                <div className="flex items-center justify-center h-full text-sm text-muted-foreground">
                  No heatmap data
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </section>

      {/* ── Portfolio ── */}
      <section>
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold">My Portfolio</h2>

            {/* Multi-select dropdown */}
            {portfolios && portfolios.length > 1 && (
              <div className="relative">
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 text-xs gap-1"
                  onClick={() => setSelectorOpen((v) => !v)}
                >
                  {allSelected
                    ? "All Portfolios"
                    : selectedIds.length === 0
                      ? "Select..."
                      : selectedIds.length === 1
                        ? portfolios.find((p) => p.id === selectedIds[0])?.name ?? "1 selected"
                        : `${selectedIds.length} selected`}
                  <ChevronsUpDown className="h-3 w-3" />
                </Button>
                {selectorOpen && (
                  <>
                    <div className="fixed inset-0 z-40" onClick={() => setSelectorOpen(false)} />
                    <div className="absolute top-8 left-0 z-50 w-52 rounded-md border bg-popover shadow-md py-1">
                      {/* Select All */}
                      <button
                        className="flex items-center gap-2 w-full px-3 py-1.5 text-xs hover:bg-accent"
                        onClick={toggleAll}
                      >
                        <div className={`w-3.5 h-3.5 rounded-sm border flex items-center justify-center ${allSelected ? "bg-primary border-primary" : "border-input"}`}>
                          {allSelected && <Check className="h-2.5 w-2.5 text-primary-foreground" />}
                        </div>
                        <span className="font-medium">Select All</span>
                      </button>
                      <div className="h-px bg-border my-1" />
                      {portfolios.map((p) => {
                        const checked = selectedIds.includes(p.id);
                        return (
                          <button
                            key={p.id}
                            className="flex items-center gap-2 w-full px-3 py-1.5 text-xs hover:bg-accent"
                            onClick={() => toggleId(p.id)}
                          >
                            <div className={`w-3.5 h-3.5 rounded-sm border flex items-center justify-center ${checked ? "bg-primary border-primary" : "border-input"}`}>
                              {checked && <Check className="h-2.5 w-2.5 text-primary-foreground" />}
                            </div>
                            <span>{p.name}</span>
                          </button>
                        );
                      })}
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
          <Link to="/portfolio">
            <Button variant="ghost" size="sm" className="h-7 text-xs">
              Manage <ArrowRight className="ml-1 h-3 w-3" />
            </Button>
          </Link>
        </div>

        {portfolios && portfolios.length > 0 ? (
          <div className="space-y-2">
            {/* Stat Strip */}
            <Card>
              <CardContent className="p-0">
                <div className="grid grid-cols-2 md:grid-cols-4 divide-x">
                  <div className="p-3">
                    <p className="text-[10px] text-muted-foreground uppercase tracking-wider">Total Value</p>
                    <p className="text-lg font-bold">{formatCurrency(totalValue)}</p>
                  </div>
                  <div className="p-3">
                    <p className="text-[10px] text-muted-foreground uppercase tracking-wider">Total Cost</p>
                    <p className="text-lg font-bold">{formatCurrency(totalCost)}</p>
                  </div>
                  <div className="p-3">
                    <p className="text-[10px] text-muted-foreground uppercase tracking-wider">Gain/Loss</p>
                    <p className={`text-lg font-bold ${totalGain >= 0 ? "text-green-600" : "text-red-600"}`}>
                      {formatCurrency(totalGain)}
                    </p>
                    {totalGainPct != null && (
                      <span className={`text-xs ${totalGainPct >= 0 ? "text-green-600" : "text-red-600"}`}>
                        {totalGainPct >= 0 ? "+" : ""}{totalGainPct.toFixed(2)}%
                      </span>
                    )}
                  </div>
                  <div className="p-3">
                    <p className="text-[10px] text-muted-foreground uppercase tracking-wider">Holdings</p>
                    <p className="text-lg font-bold">{holdings.length}</p>
                    <span className="text-xs text-muted-foreground">{portfolios.length} portfolio{portfolios.length !== 1 && "s"}</span>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Charts Row: Allocation + Performance + Holdings */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-2">
              {/* Allocation Donut */}
              <Card>
                <CardContent className="p-3">
                  <p className="text-xs font-semibold mb-2">Allocation</p>
                  <div className="h-48">
                    {allocation && allocation.by_stock.length > 0 ? (
                      <AllocationChart data={allocation.by_stock} title="By Stock" />
                    ) : (
                      <div className="flex items-center justify-center h-full text-xs text-muted-foreground">No data</div>
                    )}
                  </div>
                </CardContent>
              </Card>

              {/* Performance Chart */}
              <Card>
                <CardContent className="p-3">
                  <p className="text-xs font-semibold mb-2">Performance (3M)</p>
                  <div className="h-48">
                    {perfLoading ? (
                      <div className="flex items-center justify-center h-full">
                        <div className="text-xs text-muted-foreground animate-pulse">Loading performance...</div>
                      </div>
                    ) : performance && performance.points.length > 0 ? (
                      <PerformanceChart data={performance.points} />
                    ) : (
                      <div className="flex items-center justify-center h-full text-xs text-muted-foreground">No data</div>
                    )}
                  </div>
                </CardContent>
              </Card>

              {/* Top Holdings with Gain Bars */}
              <Card>
                <CardContent className="p-3">
                  <p className="text-xs font-semibold mb-2">Holdings</p>
                  <div className="space-y-2.5">
                    {holdings.slice(0, 6).map((h) => (
                      <div key={h.ticker}>
                        <div className="flex items-center justify-between mb-0.5">
                          <Link to={`/stock/${h.ticker}`} className="flex items-center gap-1.5">
                            <img
                              src={`https://assets.parqet.com/logos/symbol/${h.ticker}`}
                              alt=""
                              className="w-4 h-4 rounded-sm"
                              onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                            />
                            <span className="text-xs font-semibold">{h.ticker}</span>
                          </Link>
                          <span className="text-xs tabular-nums">{formatCurrency(h.market_value)}</span>
                        </div>
                        <GainBar pct={h.unrealized_gain_pct} />
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        ) : (
          <Card>
            <CardContent className="py-6 text-center text-muted-foreground text-sm">
              No portfolios yet.{" "}
              <Link to="/portfolio" className="text-blue-600 hover:underline">Create one</Link>
            </CardContent>
          </Card>
        )}
      </section>

      {/* ── Holdings News ── */}
      {holdingsNews.length > 0 && (
        <section>
          <div className="flex items-center justify-between mb-1">
            <h2 className="text-sm font-semibold">Holdings News</h2>
            <Link to="/sentiment">
              <Button variant="ghost" size="sm" className="h-7 text-xs">
                All News <ArrowRight className="ml-1 h-3 w-3" />
              </Button>
            </Link>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
            {holdingsNews.map((article) => (
              <Card key={article.id} className="hover:bg-muted/30 transition-colors">
                <CardContent className="p-3">
                  <div className="flex items-start gap-2">
                    {article.ticker && (
                      <img
                        src={`https://assets.parqet.com/logos/symbol/${article.ticker}`}
                        alt=""
                        className="w-5 h-5 rounded-sm mt-0.5 flex-shrink-0"
                        onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                      />
                    )}
                    <div className="min-w-0">
                      <a
                        href={article.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs font-medium hover:underline line-clamp-2 leading-snug"
                      >
                        {article.headline}
                      </a>
                      <div className="flex items-center gap-1.5 mt-1">
                        {article.ticker && (
                          <span className="text-[10px] font-semibold text-blue-600">{article.ticker}</span>
                        )}
                        <span className="text-[10px] text-muted-foreground">{article.source}</span>
                        {article.published_at && (
                          <span className="text-[10px] text-muted-foreground">{formatDate(article.published_at, "MMM dd")}</span>
                        )}
                        {article.sentiment_label && article.sentiment_label !== "Neutral" && (
                          <span className={`text-[10px] font-medium ${
                            article.sentiment_label === "Bullish" ? "text-green-600" : "text-red-600"
                          }`}>
                            {article.sentiment_label}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>
      )}
    </div>
  );
};

export default Dashboard;
