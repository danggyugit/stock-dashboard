import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ExternalLink, ChevronRight } from "lucide-react";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import MetricCard from "@/components/common/MetricCard";
import PriceChange from "@/components/common/PriceChange";
import SentimentBadge from "@/components/common/SentimentBadge";
import CandlestickChart from "@/components/market/CandlestickChart";
import { getStockDetail } from "@/api/market";
import { getNews } from "@/api/sentiment";
import { formatCurrency, formatNumber, formatDate } from "@/lib/utils";
import type { StockDetail as StockDetailType, NewsResponse, Period } from "@/types";

const chartPeriods: { label: string; value: Period }[] = [
  { label: "1D", value: "1d" },
  { label: "1W", value: "1w" },
  { label: "1M", value: "1m" },
  { label: "3M", value: "3m" },
  { label: "6M", value: "6m" },
  { label: "1Y", value: "1y" },
  { label: "5Y", value: "5y" },
];

const StockDetail = () => {
  const { ticker } = useParams<{ ticker: string }>();
  const [chartPeriod, setChartPeriod] = useState<Period>("1y");

  const {
    data: stock,
    isLoading: stockLoading,
    error: stockError,
  } = useQuery<StockDetailType>({
    queryKey: ["stockDetail", ticker],
    queryFn: () => getStockDetail(ticker!),
    enabled: !!ticker,
    staleTime: 60_000,
  });

  const { data: newsData } = useQuery<NewsResponse>({
    queryKey: ["stockNews", ticker],
    queryFn: () => getNews(ticker, 1),
    enabled: !!ticker,
    staleTime: 5 * 60_000,
  });

  if (!ticker) {
    return <p>No ticker specified.</p>;
  }

  if (stockError) {
    return (
      <div className="text-center py-16">
        <p className="text-destructive text-lg font-medium">
          Failed to load stock details
        </p>
        <p className="text-muted-foreground mt-2">
          {(stockError as Error).message}
        </p>
        <Link to="/screener" className="mt-4 inline-block">
          <Button variant="outline">Back to Screener</Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-1 text-sm text-muted-foreground">
        <Link to="/market" className="hover:text-foreground transition-colors">
          Market
        </Link>
        <ChevronRight className="h-3.5 w-3.5" />
        <Link
          to="/screener"
          className="hover:text-foreground transition-colors"
        >
          Screener
        </Link>
        <ChevronRight className="h-3.5 w-3.5" />
        <span className="text-foreground font-medium">{ticker}</span>
      </nav>

      {/* Header: Name + Price */}
      {stockLoading ? (
        <div className="space-y-2">
          <Skeleton className="h-10 w-48" />
          <Skeleton className="h-5 w-64" />
        </div>
      ) : stock ? (
        <div className="flex flex-col sm:flex-row sm:items-start gap-4">
          <div className="flex-1">
            <div className="flex items-center gap-3">
              <h1 className="text-3xl font-bold tracking-tight">
                {stock.ticker}
              </h1>
              <Badge variant="secondary">{stock.sector}</Badge>
              <Badge variant="outline">{stock.exchange}</Badge>
            </div>
            <p className="text-muted-foreground mt-1">{stock.name}</p>
          </div>
          <div className="sm:text-right">
            <p className="text-4xl font-bold tracking-tight">
              {stock.price != null ? formatCurrency(stock.price) : "--"}
            </p>
            <div className="mt-1">
              <PriceChange value={stock.price != null && stock.prev_close != null ? stock.price - stock.prev_close : undefined} percent={stock.change_pct ?? undefined} />
            </div>
          </div>
        </div>
      ) : null}

      {/* Candlestick Chart Section */}
      <Card className="overflow-hidden">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">Price Chart</CardTitle>
            <Tabs
              value={chartPeriod}
              onValueChange={(v) => setChartPeriod(v as Period)}
            >
              <TabsList className="h-8">
                {chartPeriods.map((p) => (
                  <TabsTrigger
                    key={p.value}
                    value={p.value}
                    className="text-xs px-2"
                  >
                    {p.label}
                  </TabsTrigger>
                ))}
              </TabsList>
            </Tabs>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          <CandlestickChart
            ticker={ticker}
            period={chartPeriod}
            height={420}
          />
        </CardContent>
      </Card>

      {/* Financial Metrics */}
      <div>
        <h2 className="text-xl font-semibold mb-4">Key Metrics</h2>
        {stockLoading ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
            {Array.from({ length: 12 }).map((_, i) => (
              <Skeleton key={i} className="h-24 w-full" />
            ))}
          </div>
        ) : stock ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
            <MetricCard
              title="Market Cap"
              value={stock.market_cap != null ? formatNumber(stock.market_cap) : "--"}
            />
            <MetricCard
              title="P/E Ratio"
              value={stock.pe_ratio != null ? stock.pe_ratio.toFixed(2) : "--"}
            />
            <MetricCard
              title="P/B Ratio"
              value={stock.pb_ratio != null ? stock.pb_ratio.toFixed(2) : "--"}
            />
            <MetricCard
              title="EPS"
              value={stock.eps != null ? formatCurrency(stock.eps) : "--"}
            />
            <MetricCard
              title="ROE"
              value={
                stock.roe != null ? `${(stock.roe * 100).toFixed(2)}%` : "--"
              }
            />
            <MetricCard
              title="Debt/Equity"
              value={
                stock.debt_to_equity != null
                  ? stock.debt_to_equity.toFixed(2)
                  : "--"
              }
            />
            <MetricCard
              title="Dividend Yield"
              value={
                stock.dividend_yield != null
                  ? `${(stock.dividend_yield * 100).toFixed(2)}%`
                  : "--"
              }
            />
            <MetricCard
              title="Beta"
              value={stock.beta != null ? stock.beta.toFixed(2) : "--"}
            />
            <MetricCard
              title="52W High"
              value={stock.fifty_two_week_high != null ? formatCurrency(stock.fifty_two_week_high) : "--"}
            />
            <MetricCard
              title="52W Low"
              value={stock.fifty_two_week_low != null ? formatCurrency(stock.fifty_two_week_low) : "--"}
            />
            <MetricCard
              title="Avg Volume"
              value={stock.avg_volume != null ? formatNumber(stock.avg_volume) : "--"}
            />
            <MetricCard
              title="P/S Ratio"
              value={stock.ps_ratio != null ? stock.ps_ratio.toFixed(2) : "--"}
            />
          </div>
        ) : null}
      </div>

      {/* Company Description */}
      {stock?.description && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">About {stock.name}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground leading-relaxed">
              {stock.description}
            </p>
          </CardContent>
        </Card>
      )}

      <Separator />

      {/* Recent News */}
      <div>
        <h2 className="text-xl font-semibold mb-4">Recent News</h2>
        {newsData && newsData.articles.length > 0 ? (
          <div className="space-y-3">
            {newsData.articles.slice(0, 10).map((article) => (
              <Card key={article.id}>
                <CardContent className="py-3 flex items-start gap-3">
                  <div className="flex-1 min-w-0">
                    <a
                      href={article.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-medium text-sm hover:underline flex items-center gap-1"
                    >
                      {article.headline}
                      <ExternalLink className="h-3 w-3 flex-shrink-0" />
                    </a>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-xs text-muted-foreground">
                        {article.source}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {formatDate(article.published_at)}
                      </span>
                      {article.sentiment_label && (
                        <SentimentBadge label={article.sentiment_label} />
                      )}
                    </div>
                    {article.ai_summary && (
                      <p className="text-xs text-muted-foreground mt-1">
                        {article.ai_summary}
                      </p>
                    )}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            No news available for {ticker}
          </p>
        )}
      </div>
    </div>
  );
};

export default StockDetail;
