import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { RefreshCw, TrendingUp, TrendingDown } from "lucide-react";
import ChartContainer from "@/components/common/ChartContainer";
import Heatmap from "@/components/market/Heatmap";
import SectorBar from "@/components/market/SectorBar";
import { getHeatmapData, refreshMarketData } from "@/api/market";
import { formatCurrency, formatPercent, formatNumber } from "@/lib/utils";
import type { HeatmapResponse, HeatmapStock, Period } from "@/types";

const periods: { label: string; value: Period }[] = [
  { label: "1D", value: "1d" },
  { label: "1W", value: "1w" },
  { label: "1M", value: "1m" },
  { label: "3M", value: "3m" },
  { label: "YTD", value: "ytd" },
  { label: "1Y", value: "1y" },
];

interface RankedStock extends HeatmapStock {
  sector: string;
}

const Market = () => {
  const [selectedPeriod, setSelectedPeriod] = useState<Period>("1d");
  const [focusSector, setFocusSector] = useState<string | null>(null);
  const navigate = useNavigate();

  const {
    data: heatmapData,
    isLoading,
    error,
    refetch,
  } = useQuery<HeatmapResponse>({
    queryKey: ["heatmap", selectedPeriod],
    queryFn: () => getHeatmapData(selectedPeriod),
    staleTime: 5 * 60_000,
  });

  const handleRefresh = async () => {
    await refreshMarketData();
    refetch();
  };

  const isEmpty =
    !isLoading && !error && (!heatmapData || heatmapData.sectors.length === 0);

  // Compute top gainers and losers
  const { topGainers, topLosers } = useMemo(() => {
    if (!heatmapData) return { topGainers: [], topLosers: [] };

    const allStocks: RankedStock[] = heatmapData.sectors.flatMap((sector) =>
      sector.stocks.map((stock) => ({ ...stock, sector: sector.name })),
    );

    const validStocks = allStocks.filter(
      (s) => s.change_pct !== null && s.change_pct !== undefined,
    );

    const sorted = [...validStocks].sort(
      (a, b) => (b.change_pct ?? 0) - (a.change_pct ?? 0),
    );

    return {
      topGainers: sorted.slice(0, 5),
      topLosers: sorted.slice(-5).reverse(),
    };
  }, [heatmapData]);

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Market Heatmap</h1>
          <p className="text-muted-foreground">
            S&amp;P 500 sectors and stocks by market cap and performance.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={handleRefresh}>
          <RefreshCw className="h-4 w-4 mr-1" />
          Refresh
        </Button>
      </div>

      {/* Period Tabs */}
      <Tabs
        value={selectedPeriod}
        onValueChange={(v) => setSelectedPeriod(v as Period)}
      >
        <TabsList>
          {periods.map((p) => (
            <TabsTrigger key={p.value} value={p.value}>
              {p.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {/* Sector Summary Bar */}
      {heatmapData && heatmapData.sectors.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-muted-foreground">
              Sectors
            </h2>
            {focusSector && (
              <button
                onClick={() => setFocusSector(null)}
                className="text-xs text-muted-foreground hover:text-foreground transition-colors"
              >
                Clear filter
              </button>
            )}
          </div>
          <SectorBar
            sectors={heatmapData.sectors}
            focusSector={focusSector}
            onSectorClick={setFocusSector}
          />
        </div>
      )}

      {/* Heatmap Area */}
      <ChartContainer
        isLoading={isLoading}
        error={error as Error | null}
        isEmpty={isEmpty}
        emptyMessage="No heatmap data available for this period"
        height="h-[600px]"
      >
        {heatmapData && (
          <Heatmap
            data={heatmapData}
            isLoading={isLoading}
            focusSector={focusSector}
          />
        )}
      </ChartContainer>

      {/* Top Gainers / Losers */}
      {heatmapData && (topGainers.length > 0 || topLosers.length > 0) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Top Gainers */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-base">
                <TrendingUp className="h-4 w-4 text-green-500" />
                Top Gainers
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-1">
                <div className="grid grid-cols-[1fr_auto_auto_auto] gap-3 text-xs text-muted-foreground font-medium pb-1 border-b">
                  <span>Ticker</span>
                  <span className="text-right">Price</span>
                  <span className="text-right">Change</span>
                  <span className="text-right">Mkt Cap</span>
                </div>
                {topGainers.map((stock) => (
                  <button
                    key={stock.ticker}
                    onClick={() => navigate(`/stock/${stock.ticker}`)}
                    className="grid grid-cols-[1fr_auto_auto_auto] gap-3 w-full items-center py-1.5 hover:bg-muted/50 rounded px-1 transition-colors text-left"
                  >
                    <div>
                      <span className="font-semibold text-sm">
                        {stock.ticker}
                      </span>
                      <span className="text-xs text-muted-foreground ml-1.5 hidden sm:inline">
                        {stock.name.length > 20
                          ? stock.name.slice(0, 19) + "..."
                          : stock.name}
                      </span>
                    </div>
                    <span className="text-sm tabular-nums text-right">
                      {formatCurrency(stock.price)}
                    </span>
                    <span className="text-sm font-medium text-green-500 tabular-nums text-right">
                      {formatPercent(stock.change_pct)}
                    </span>
                    <span className="text-xs text-muted-foreground tabular-nums text-right">
                      ${formatNumber(stock.market_cap)}
                    </span>
                  </button>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Top Losers */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-base">
                <TrendingDown className="h-4 w-4 text-red-500" />
                Top Losers
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-1">
                <div className="grid grid-cols-[1fr_auto_auto_auto] gap-3 text-xs text-muted-foreground font-medium pb-1 border-b">
                  <span>Ticker</span>
                  <span className="text-right">Price</span>
                  <span className="text-right">Change</span>
                  <span className="text-right">Mkt Cap</span>
                </div>
                {topLosers.map((stock) => (
                  <button
                    key={stock.ticker}
                    onClick={() => navigate(`/stock/${stock.ticker}`)}
                    className="grid grid-cols-[1fr_auto_auto_auto] gap-3 w-full items-center py-1.5 hover:bg-muted/50 rounded px-1 transition-colors text-left"
                  >
                    <div>
                      <span className="font-semibold text-sm">
                        {stock.ticker}
                      </span>
                      <span className="text-xs text-muted-foreground ml-1.5 hidden sm:inline">
                        {stock.name.length > 20
                          ? stock.name.slice(0, 19) + "..."
                          : stock.name}
                      </span>
                    </div>
                    <span className="text-sm tabular-nums text-right">
                      {formatCurrency(stock.price)}
                    </span>
                    <span className="text-sm font-medium text-red-500 tabular-nums text-right">
                      {formatPercent(stock.change_pct)}
                    </span>
                    <span className="text-xs text-muted-foreground tabular-nums text-right">
                      ${formatNumber(stock.market_cap)}
                    </span>
                  </button>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
};

export default Market;
