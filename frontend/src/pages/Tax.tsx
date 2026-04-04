import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { useQuery, useQueries } from "@tanstack/react-query";
import { ArrowLeft, Calculator, AlertTriangle } from "lucide-react";
import type { ColumnDef } from "@tanstack/react-table";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import MetricCard from "@/components/common/MetricCard";
import DataTable from "@/components/common/DataTable";
import PortfolioMultiSelect from "@/components/common/PortfolioMultiSelect";
import { getPortfolios, getTax } from "@/api/portfolio";
import { formatCurrency, formatDate } from "@/lib/utils";
import type { Portfolio, TaxSummary, Trade } from "@/types";

const currentYear = new Date().getFullYear();
const years = Array.from({ length: 5 }, (_, i) => currentYear - i);

const Tax = () => {
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [year, setYear] = useState(currentYear);

  const { data: portfolios, isLoading: portfoliosLoading } = useQuery<
    Portfolio[]
  >({
    queryKey: ["portfolios"],
    queryFn: getPortfolios,
    staleTime: 60_000,
  });

  useEffect(() => {
    if (portfolios && portfolios.length > 0 && selectedIds.length === 0) {
      setSelectedIds(portfolios.map((p) => p.id));
    }
  }, [portfolios, selectedIds.length]);

  const taxQueries = useQueries({
    queries: selectedIds.map((id) => ({
      queryKey: ["tax", id, year],
      queryFn: () => getTax(id, year),
      staleTime: 5 * 60_000,
      enabled: true,
    })),
  });

  const taxLoading = taxQueries.some((q) => q.isLoading);

  // Merge tax data from all selected portfolios
  const taxData: TaxSummary | null = (() => {
    const allData = taxQueries.map((q) => q.data).filter(Boolean) as TaxSummary[];
    if (allData.length === 0) return null;
    return {
      year,
      realized_gains: allData.reduce((s, d) => s + d.realized_gains, 0),
      realized_losses: allData.reduce((s, d) => s + d.realized_losses, 0),
      net_gain: allData.reduce((s, d) => s + d.net_gain, 0),
      short_term_gain: allData.reduce((s, d) => s + d.short_term_gain, 0),
      long_term_gain: allData.reduce((s, d) => s + d.long_term_gain, 0),
      short_term_loss: allData.reduce((s, d) => s + d.short_term_loss, 0),
      long_term_loss: allData.reduce((s, d) => s + d.long_term_loss, 0),
      trades: allData.flatMap((d) => d.trades),
    };
  })();

  const columns: ColumnDef<Trade, unknown>[] = [
    {
      accessorKey: "ticker",
      header: "Ticker",
      cell: ({ row }) => (
        <Link
          to={`/stock/${row.original.ticker}`}
          className="font-medium hover:underline"
        >
          {row.original.ticker}
        </Link>
      ),
    },
    {
      accessorKey: "trade_type",
      header: "Type",
      cell: ({ row }) => (
        <Badge
          variant={
            row.original.trade_type === "SELL" ? "destructive" : "default"
          }
        >
          {row.original.trade_type}
        </Badge>
      ),
    },
    {
      accessorKey: "trade_date",
      header: "Trade Date",
      cell: ({ row }) => formatDate(row.original.trade_date),
    },
    {
      accessorKey: "quantity",
      header: "Qty",
      cell: ({ row }) => row.original.quantity.toFixed(2),
    },
    {
      accessorKey: "price",
      header: "Price",
      cell: ({ row }) => formatCurrency(row.original.price),
    },
    {
      accessorKey: "commission",
      header: "Commission",
      cell: ({ row }) => formatCurrency(row.original.commission),
    },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <Link to="/portfolio">
          <Button variant="ghost" size="sm" className="mb-2">
            <ArrowLeft className="h-4 w-4 mr-1" />
            Back to Portfolio
          </Button>
        </Link>
        <h1 className="text-3xl font-bold tracking-tight">Tax Summary</h1>
        <p className="text-muted-foreground">
          Capital gains calculation for tax reporting.
        </p>
      </div>

      {/* Controls */}
      <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center">
        {portfoliosLoading ? (
          <Skeleton className="h-9 w-48" />
        ) : portfolios && portfolios.length > 0 ? (
          <PortfolioMultiSelect
            portfolios={portfolios}
            selectedIds={selectedIds}
            onSelectionChange={setSelectedIds}
          />
        ) : null}

        <Select
          value={year.toString()}
          onValueChange={(v) => setYear(Number(v))}
        >
          <SelectTrigger className="w-32">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {years.map((y) => (
              <SelectItem key={y} value={y.toString()}>
                {y}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {selectedIds.length > 0 && (
        <>
          {/* Summary Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
            {taxLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-24 w-full" />
              ))
            ) : taxData ? (
              <>
                <MetricCard
                  title="Realized Gains"
                  value={formatCurrency(taxData.realized_gains)}
                  icon={<Calculator className="h-4 w-4" />}
                />
                <MetricCard
                  title="Realized Losses"
                  value={formatCurrency(taxData.realized_losses)}
                  icon={<Calculator className="h-4 w-4" />}
                />
                <MetricCard
                  title="Net Gain/Loss"
                  value={formatCurrency(taxData.net_gain)}
                  changePct={
                    taxData.net_gain !== 0 && taxData.realized_gains !== 0
                      ? (taxData.net_gain / taxData.realized_gains) * 100
                      : undefined
                  }
                />
                <MetricCard
                  title="Short-term Gains"
                  value={formatCurrency(taxData.short_term_gain)}
                />
                <MetricCard
                  title="Long-term Gains"
                  value={formatCurrency(taxData.long_term_gain)}
                />
              </>
            ) : null}
          </div>

          {/* Tax Note */}
          <Card className="border-yellow-200 bg-yellow-50/50 dark:border-yellow-800 dark:bg-yellow-950/20">
            <CardContent className="py-3 flex items-start gap-2">
              <AlertTriangle className="h-4 w-4 text-yellow-600 mt-0.5 shrink-0" />
              <div className="text-xs text-muted-foreground">
                <p className="font-medium text-yellow-700 dark:text-yellow-500">
                  Disclaimer
                </p>
                <p>
                  This is an estimate only. Short-term capital gains (held &lt;
                  1 year) are taxed as ordinary income. Long-term capital gains
                  (held &gt; 1 year) have preferential tax rates (0%, 15%, or
                  20%). Consult a tax professional for accurate tax advice.
                </p>
              </div>
            </CardContent>
          </Card>

          {/* Trades Table */}
          <div>
            <h2 className="text-xl font-semibold mb-4">
              Realized Gain/Loss Trades
            </h2>
            {taxLoading ? (
              <div className="space-y-2">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Skeleton key={i} className="h-10 w-full" />
                ))}
              </div>
            ) : taxData && taxData.trades.length > 0 ? (
              <DataTable data={taxData.trades} columns={columns} />
            ) : (
              <Card>
                <CardContent className="py-8 text-center text-muted-foreground">
                  No realized gains/losses for {year}.
                </CardContent>
              </Card>
            )}
          </div>
        </>
      )}
    </div>
  );
};

export default Tax;
