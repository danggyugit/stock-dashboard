import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  TrendingUp,
  BarChart3,
  Briefcase,
  Brain,
  ArrowRight,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import MetricCard from "@/components/common/MetricCard";
import PriceChange from "@/components/common/PriceChange";
import { getIndices } from "@/api/market";
import { getPortfolios } from "@/api/portfolio";
import { getFearGreed } from "@/api/sentiment";
import { formatCurrency } from "@/lib/utils";
import type { IndexInfo, Portfolio, FearGreedData } from "@/types";

const Dashboard = () => {
  const {
    data: indices,
    isLoading: indicesLoading,
    error: indicesError,
  } = useQuery<IndexInfo[]>({
    queryKey: ["indices"],
    queryFn: getIndices,
    staleTime: 60_000,
  });

  const {
    data: portfolios,
    isLoading: portfoliosLoading,
  } = useQuery<Portfolio[]>({
    queryKey: ["portfolios"],
    queryFn: getPortfolios,
    staleTime: 60_000,
  });

  const {
    data: fearGreed,
    isLoading: fgLoading,
  } = useQuery<FearGreedData>({
    queryKey: ["fearGreed"],
    queryFn: getFearGreed,
    staleTime: 60_000,
  });

  const totalPortfolioValue = portfolios?.reduce(
    (sum, p) => sum + (p.total_value ?? 0),
    0,
  ) ?? 0;

  const totalPortfolioGain = portfolios?.reduce(
    (sum, p) => sum + (p.total_gain ?? 0),
    0,
  ) ?? 0;

  const getFearGreedColor = (score: number): string => {
    if (score <= 25) return "text-red-600";
    if (score <= 45) return "text-orange-500";
    if (score <= 55) return "text-yellow-500";
    if (score <= 75) return "text-green-500";
    return "text-green-600";
  };

  return (
    <div className="space-y-8">
      {/* Page Title */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground">
          Market overview, portfolio summary, and sentiment at a glance.
        </p>
      </div>

      {/* Major Indices */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold flex items-center gap-2">
            <TrendingUp className="h-5 w-5" />
            Major Indices
          </h2>
          <Link to="/market">
            <Button variant="ghost" size="sm">
              View Market <ArrowRight className="ml-1 h-4 w-4" />
            </Button>
          </Link>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {indicesLoading ? (
            Array.from({ length: 3 }).map((_, i) => (
              <Card key={i}>
                <CardHeader className="pb-2">
                  <Skeleton className="h-4 w-24" />
                </CardHeader>
                <CardContent>
                  <Skeleton className="h-8 w-32 mb-2" />
                  <Skeleton className="h-4 w-20" />
                </CardContent>
              </Card>
            ))
          ) : indicesError ? (
            <Card className="col-span-3">
              <CardContent className="py-8 text-center text-muted-foreground">
                Failed to load indices. Backend may not be running.
              </CardContent>
            </Card>
          ) : (
            indices?.map((idx) => (
              <MetricCard
                key={idx.ticker}
                title={idx.name}
                value={formatCurrency(idx.price, "USD", 2)}
                change={idx.change}
                changePct={idx.change_pct}
              />
            ))
          )}
        </div>
      </section>

      {/* Market + Portfolio + Sentiment Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Market Section */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <BarChart3 className="h-4 w-4" />
              Market Overview
            </CardTitle>
          </CardHeader>
          <CardContent>
            {indicesLoading ? (
              <div className="space-y-3">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Skeleton key={i} className="h-6 w-full" />
                ))}
              </div>
            ) : indices && indices.length > 0 ? (
              <div className="space-y-3">
                {indices.map((idx) => (
                  <div
                    key={idx.ticker}
                    className="flex items-center justify-between"
                  >
                    <span className="text-sm font-medium">{idx.ticker}</span>
                    <PriceChange percent={idx.change_pct} />
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-4">
                No market data available
              </p>
            )}
            <Link to="/market" className="block mt-4">
              <Button variant="outline" size="sm" className="w-full">
                View Heatmap
              </Button>
            </Link>
          </CardContent>
        </Card>

        {/* Portfolio Section */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Briefcase className="h-4 w-4" />
              Portfolio Summary
            </CardTitle>
          </CardHeader>
          <CardContent>
            {portfoliosLoading ? (
              <div className="space-y-3">
                <Skeleton className="h-8 w-full" />
                <Skeleton className="h-6 w-3/4" />
              </div>
            ) : portfolios && portfolios.length > 0 ? (
              <div className="space-y-4">
                <div>
                  <p className="text-sm text-muted-foreground">Total Value</p>
                  <p className="text-2xl font-bold">
                    {formatCurrency(totalPortfolioValue)}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">
                    Total Gain/Loss
                  </p>
                  <PriceChange value={totalPortfolioGain} />
                </div>
                <div className="text-sm text-muted-foreground">
                  {portfolios.length} portfolio
                  {portfolios.length !== 1 && "s"}
                </div>
              </div>
            ) : (
              <div className="text-center py-4">
                <p className="text-sm text-muted-foreground mb-2">
                  No portfolios yet
                </p>
                <Link to="/portfolio">
                  <Button variant="outline" size="sm">
                    Create Portfolio
                  </Button>
                </Link>
              </div>
            )}
            <Link to="/portfolio" className="block mt-4">
              <Button variant="outline" size="sm" className="w-full">
                Manage Portfolio
              </Button>
            </Link>
          </CardContent>
        </Card>

        {/* Sentiment Section */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Brain className="h-4 w-4" />
              Market Sentiment
            </CardTitle>
          </CardHeader>
          <CardContent>
            {fgLoading ? (
              <div className="space-y-3">
                <Skeleton className="h-16 w-16 rounded-full mx-auto" />
                <Skeleton className="h-6 w-32 mx-auto" />
              </div>
            ) : fearGreed ? (
              <div className="text-center space-y-3">
                <div
                  className={`text-5xl font-bold ${getFearGreedColor(fearGreed.score)}`}
                >
                  {Math.round(fearGreed.score)}
                </div>
                <p className="text-sm font-medium">{fearGreed.label}</p>
                <p className="text-xs text-muted-foreground">
                  Fear &amp; Greed Index
                </p>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-4">
                Sentiment data unavailable
              </p>
            )}
            <Link to="/sentiment" className="block mt-4">
              <Button variant="outline" size="sm" className="w-full">
                View Sentiment
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default Dashboard;
