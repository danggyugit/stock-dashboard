import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { X, Plus, BarChart3 } from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import TickerSearch from "@/components/common/TickerSearch";
import PriceChange from "@/components/common/PriceChange";
import ChartContainer from "@/components/common/ChartContainer";
import { getCompareData } from "@/api/market";
import { useAppStore } from "@/stores/appStore";
import { formatCurrency, formatNumber } from "@/lib/utils";
import type { CompareResponse, CompareStock, Period } from "@/types";

const periods: { label: string; value: Period }[] = [
  { label: "1M", value: "1m" },
  { label: "3M", value: "3m" },
  { label: "6M", value: "6m" },
  { label: "1Y", value: "1y" },
];

const LINE_COLORS = ["#3b82f6", "#ef4444", "#22c55e", "#f59e0b", "#a855f7"];

const Compare = () => {
  const {
    compareTickers,
    addCompareTicker,
    removeCompareTicker,
    clearCompareTickers,
  } = useAppStore();
  const [period, setPeriod] = useState<Period>("1y");

  const {
    data: compareData,
    isLoading,
    error,
  } = useQuery<CompareResponse>({
    queryKey: ["compare", compareTickers, period],
    queryFn: () => getCompareData(compareTickers, period),
    enabled: compareTickers.length >= 2,
    staleTime: 2 * 60_000,
  });

  const handleAddTicker = (ticker: string) => {
    addCompareTicker(ticker.toUpperCase());
  };

  // Build normalized chart data: start point = 100%
  const normalizedData = useMemo(() => {
    if (!compareData || compareData.stocks.length === 0) return [];

    // Find the stock with the most data points to use as date reference
    const allStocks = compareData.stocks;

    // Get all unique dates from all stocks, then sort
    const dateSet = new Set<string>();
    for (const stock of allStocks) {
      for (const point of stock.chart_data) {
        dateSet.add(point.date);
      }
    }
    const allDates = Array.from(dateSet).sort();

    // Build a lookup: ticker -> date -> close
    const lookups = new Map<string, Map<string, number>>();
    const basePrices = new Map<string, number>();

    for (const stock of allStocks) {
      const dateMap = new Map<string, number>();
      for (const point of stock.chart_data) {
        dateMap.set(point.date, point.close);
      }
      lookups.set(stock.ticker, dateMap);
      // Base price is the first available close price
      if (stock.chart_data.length > 0) {
        basePrices.set(stock.ticker, stock.chart_data[0].close);
      }
    }

    // For each date, compute normalized value = (close / base) * 100
    return allDates.map((date) => {
      const entry: Record<string, string | number> = { date };
      for (const stock of allStocks) {
        const dateMap = lookups.get(stock.ticker);
        const base = basePrices.get(stock.ticker);
        const close = dateMap?.get(date);
        if (close !== undefined && base !== undefined && base !== 0) {
          entry[stock.ticker] = Number(((close / base) * 100).toFixed(2));
        }
      }
      return entry;
    });
  }, [compareData]);

  const formatMetricValue = (
    stock: CompareStock,
    metric: string,
  ): string | number => {
    switch (metric) {
      case "Price":
        return formatCurrency(stock.price);
      case "Market Cap":
        return formatNumber(stock.market_cap);
      case "P/E":
        return stock.pe_ratio != null ? stock.pe_ratio.toFixed(2) : "--";
      case "P/B":
        return stock.pb_ratio != null ? stock.pb_ratio.toFixed(2) : "--";
      case "Div Yield":
        return stock.dividend_yield != null
          ? `${(stock.dividend_yield * 100).toFixed(2)}%`
          : "--";
      case "Beta":
        return stock.beta != null ? stock.beta.toFixed(2) : "--";
      case "ROE":
        return stock.roe != null
          ? `${(stock.roe * 100).toFixed(2)}%`
          : "--";
      case "EPS":
        return stock.eps != null ? formatCurrency(stock.eps) : "--";
      default:
        return "--";
    }
  };

  const metricRows = [
    "Price",
    "Market Cap",
    "P/E",
    "P/B",
    "Div Yield",
    "Beta",
    "ROE",
    "EPS",
  ];

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Compare Stocks</h1>
        <p className="text-muted-foreground">
          Compare performance and metrics of up to 5 stocks side by side.
        </p>
      </div>

      {/* Ticker Selection */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Plus className="h-4 w-4" />
            Select Stocks to Compare
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="w-full sm:w-72">
              <TickerSearch
                onSelect={handleAddTicker}
                placeholder="Add a stock..."
              />
            </div>
            <div className="flex flex-wrap gap-2 items-center">
              {compareTickers.map((ticker, idx) => (
                <Badge
                  key={ticker}
                  variant="secondary"
                  className="text-sm py-1 px-3 gap-1"
                  style={{
                    borderLeft: `3px solid ${LINE_COLORS[idx % LINE_COLORS.length]}`,
                  }}
                >
                  {ticker}
                  <button
                    type="button"
                    onClick={() => removeCompareTicker(ticker)}
                    className="ml-1 hover:text-destructive"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </Badge>
              ))}
              {compareTickers.length > 0 && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={clearCompareTickers}
                >
                  Clear All
                </Button>
              )}
            </div>
          </div>
          {compareTickers.length < 2 && (
            <p className="text-sm text-muted-foreground mt-3">
              Add at least 2 stocks to compare.
            </p>
          )}
          {compareTickers.length >= 5 && (
            <p className="text-sm text-orange-500 mt-2">
              Maximum 5 stocks for comparison.
            </p>
          )}
        </CardContent>
      </Card>

      {compareTickers.length < 2 && (
        <Card>
          <CardContent className="py-16 text-center">
            <BarChart3 className="h-12 w-12 mx-auto text-muted-foreground/40 mb-4" />
            <p className="text-lg font-medium text-muted-foreground">
              Add stocks to get started
            </p>
            <p className="text-sm text-muted-foreground mt-1">
              Search and add at least 2 stocks above to see comparison charts
              and metrics.
            </p>
          </CardContent>
        </Card>
      )}

      {compareTickers.length >= 2 && (
        <>
          {/* Period Tabs */}
          <Tabs
            value={period}
            onValueChange={(v) => setPeriod(v as Period)}
          >
            <TabsList>
              {periods.map((p) => (
                <TabsTrigger key={p.value} value={p.value}>
                  {p.label}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>

          {/* Normalized Performance Chart */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">
                Normalized Performance (Base = 100%)
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ChartContainer
                isLoading={isLoading}
                error={error as Error | null}
                isEmpty={!compareData || compareData.stocks.length === 0}
                height="h-80"
              >
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={normalizedData}>
                    <XAxis
                      dataKey="date"
                      tick={{ fontSize: 11 }}
                      tickFormatter={(val: string) => {
                        const d = new Date(val);
                        return `${d.getMonth() + 1}/${d.getDate()}`;
                      }}
                      minTickGap={40}
                    />
                    <YAxis
                      tick={{ fontSize: 11 }}
                      domain={["auto", "auto"]}
                      tickFormatter={(val: number) => `${val}%`}
                    />
                    <Tooltip
                      labelFormatter={(label) => {
                        const d = new Date(String(label));
                        return d.toLocaleDateString("en-US", {
                          year: "numeric",
                          month: "short",
                          day: "numeric",
                        });
                      }}
                      formatter={(value, name) => [
                        `${Number(value).toFixed(2)}%`,
                        String(name),
                      ]}
                    />
                    <Legend />
                    {compareData?.stocks.map((stock, idx) => (
                      <Line
                        key={stock.ticker}
                        type="monotone"
                        dataKey={stock.ticker}
                        stroke={LINE_COLORS[idx % LINE_COLORS.length]}
                        strokeWidth={2}
                        dot={false}
                        connectNulls
                      />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </ChartContainer>
            </CardContent>
          </Card>

          {/* Comparison Table */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Metrics Comparison</CardTitle>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="space-y-2">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <div
                      key={i}
                      className="h-8 bg-muted rounded animate-pulse"
                    />
                  ))}
                </div>
              ) : compareData && compareData.stocks.length > 0 ? (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-[120px]">Metric</TableHead>
                        {compareData.stocks.map((s, idx) => (
                          <TableHead key={s.ticker} className="text-center">
                            <span
                              className="font-semibold"
                              style={{
                                color:
                                  LINE_COLORS[idx % LINE_COLORS.length],
                              }}
                            >
                              {s.ticker}
                            </span>
                            <span className="block text-xs font-normal text-muted-foreground">
                              {s.name}
                            </span>
                          </TableHead>
                        ))}
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {/* Change row with special PriceChange component */}
                      <TableRow>
                        <TableCell className="font-medium">Change</TableCell>
                        {compareData.stocks.map((s) => (
                          <TableCell key={s.ticker} className="text-center">
                            <PriceChange
                              percent={s.change_pct}
                              showIcon={false}
                            />
                          </TableCell>
                        ))}
                      </TableRow>
                      {metricRows.map((metric) => (
                        <TableRow key={metric}>
                          <TableCell className="font-medium">
                            {metric}
                          </TableCell>
                          {compareData.stocks.map((s) => (
                            <TableCell
                              key={s.ticker}
                              className="text-center"
                            >
                              {formatMetricValue(s, metric)}
                            </TableCell>
                          ))}
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground text-center py-4">
                  No comparison data available
                </p>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
};

export default Compare;
