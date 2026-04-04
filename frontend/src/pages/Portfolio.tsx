import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Briefcase,
  Plus,
  Trash2,
  BarChart3,
  Calendar,
  Receipt,
  TrendingUp,
  DollarSign,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import MetricCard from "@/components/common/MetricCard";
import PriceChange from "@/components/common/PriceChange";
import DataTable from "@/components/common/DataTable";
import ChartContainer from "@/components/common/ChartContainer";
import AllocationChart from "@/components/portfolio/AllocationChart";
import PerformanceChart from "@/components/portfolio/PerformanceChart";
import {
  getPortfolios,
  createPortfolio,
  getPortfolioDetail,
  deletePortfolio,
  getAllocation,
  getPerformance,
} from "@/api/portfolio";
import { formatCurrency } from "@/lib/utils";
import type {
  Portfolio as PortfolioType,
  Holding,
  AllocationResponse,
  PerformanceResponse,
  Period,
} from "@/types";
import type { ColumnDef } from "@tanstack/react-table";

const PERF_PERIODS: { label: string; value: Period }[] = [
  { label: "1M", value: "1m" },
  { label: "3M", value: "3m" },
  { label: "6M", value: "6m" },
  { label: "YTD", value: "ytd" },
  { label: "1Y", value: "1y" },
];

const Portfolio = () => {
  const queryClient = useQueryClient();
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<
    number | null
  >(null);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [perfPeriod, setPerfPeriod] = useState<Period>("1m");

  const { data: portfolios, isLoading: portfoliosLoading } = useQuery<
    PortfolioType[]
  >({
    queryKey: ["portfolios"],
    queryFn: getPortfolios,
    staleTime: 60_000,
  });

  const activeId = selectedPortfolioId ?? portfolios?.[0]?.id ?? null;

  const { data: portfolio, isLoading: detailLoading } =
    useQuery<PortfolioType>({
      queryKey: ["portfolioDetail", activeId],
      queryFn: () => getPortfolioDetail(activeId!),
      enabled: activeId !== null,
      staleTime: 60_000,
    });

  const { data: allocation, isLoading: allocLoading } =
    useQuery<AllocationResponse>({
      queryKey: ["allocation", activeId],
      queryFn: () => getAllocation(activeId!),
      enabled: activeId !== null,
      staleTime: 60_000,
    });

  const { data: performance, isLoading: perfLoading } =
    useQuery<PerformanceResponse>({
      queryKey: ["performance", activeId, perfPeriod],
      queryFn: () => getPerformance(activeId!, perfPeriod),
      enabled: activeId !== null,
      staleTime: 60_000,
    });

  const createMutation = useMutation({
    mutationFn: () =>
      createPortfolio({ name: newName, description: newDesc }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["portfolios"] });
      setNewName("");
      setNewDesc("");
      setDialogOpen(false);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deletePortfolio(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["portfolios"] });
      setSelectedPortfolioId(null);
      setDeleteDialogOpen(false);
    },
  });

  const holdings = portfolio?.holdings ?? [];

  const computeGainPct = (h: Holding): number => {
    if (h.unrealized_gain_pct != null) return h.unrealized_gain_pct;
    if (h.total_cost && h.total_cost !== 0) return (h.unrealized_gain / h.total_cost) * 100;
    return 0;
  };

  const totalGainPct = (() => {
    if (portfolio?.total_gain_pct != null) return portfolio.total_gain_pct;
    const cost = portfolio?.total_cost;
    const gain = portfolio?.total_gain;
    if (cost && cost !== 0 && gain != null) return (gain / cost) * 100;
    return null;
  })();

  const holdingsColumns: ColumnDef<Holding, unknown>[] = [
    {
      accessorKey: "ticker",
      header: "Ticker",
      cell: ({ row }) => (
        <Link
          to={`/stock/${row.original.ticker}`}
          className="font-medium hover:underline text-blue-600 dark:text-blue-400"
        >
          {row.original.ticker}
        </Link>
      ),
    },
    {
      accessorKey: "name",
      header: "Name",
      cell: ({ row }) => (
        <span className="text-sm truncate max-w-[160px] block">
          {row.original.name}
        </span>
      ),
    },
    {
      accessorKey: "quantity",
      header: "Shares",
      cell: ({ row }) => row.original.quantity.toFixed(2),
    },
    {
      accessorKey: "avg_cost",
      header: "Avg Cost",
      cell: ({ row }) => formatCurrency(row.original.avg_cost),
    },
    {
      accessorKey: "current_price",
      header: "Current",
      cell: ({ row }) => formatCurrency(row.original.current_price),
    },
    {
      accessorKey: "market_value",
      header: "Value",
      cell: ({ row }) => formatCurrency(row.original.market_value),
    },
    {
      accessorKey: "unrealized_gain",
      header: "Gain/Loss",
      cell: ({ row }) => {
        const pct = computeGainPct(row.original);
        return <PriceChange value={row.original.unrealized_gain} percent={pct} />;
      },
    },
  ];

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Portfolio</h1>
          <p className="text-muted-foreground">
            Track holdings, performance, and asset allocation.
          </p>
        </div>
        <div className="flex gap-2">
          <Link to="/portfolio/trades">
            <Button variant="outline" size="sm">
              <Receipt className="h-4 w-4 mr-1" />
              Trades
            </Button>
          </Link>
          <Link to="/portfolio/dividends">
            <Button variant="outline" size="sm">
              <Calendar className="h-4 w-4 mr-1" />
              Dividends
            </Button>
          </Link>
          <Link to="/portfolio/tax">
            <Button variant="outline" size="sm">
              <Receipt className="h-4 w-4 mr-1" />
              Tax
            </Button>
          </Link>
        </div>
      </div>

      {/* Portfolio Selector + Create */}
      <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center">
        {portfoliosLoading ? (
          <Skeleton className="h-9 w-48" />
        ) : portfolios && portfolios.length > 0 ? (
          <Select
            value={activeId?.toString() ?? ""}
            onValueChange={(v) => setSelectedPortfolioId(Number(v))}
          >
            <SelectTrigger className="w-56">
              <SelectValue placeholder="Select portfolio" />
            </SelectTrigger>
            <SelectContent>
              {portfolios.map((p) => (
                <SelectItem key={p.id} value={p.id.toString()}>
                  {p.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        ) : (
          <p className="text-sm text-muted-foreground">No portfolios yet.</p>
        )}

        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger render={<Button size="sm" />}>
            <Plus className="h-4 w-4 mr-1" />
            New Portfolio
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create Portfolio</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 mt-2">
              <div className="space-y-1.5">
                <Label>Name</Label>
                <Input
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="e.g. Long-term Growth"
                />
              </div>
              <div className="space-y-1.5">
                <Label>Description (optional)</Label>
                <Input
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                  placeholder="e.g. Core holdings for retirement"
                />
              </div>
              <Button
                onClick={() => createMutation.mutate()}
                disabled={!newName.trim() || createMutation.isPending}
                className="w-full"
              >
                {createMutation.isPending ? "Creating..." : "Create"}
              </Button>
            </div>
          </DialogContent>
        </Dialog>

        {activeId && (
          <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
            <DialogTrigger
              render={
                <Button variant="ghost" size="sm" className="text-destructive" />
              }
            >
              <Trash2 className="h-4 w-4 mr-1" />
              Delete
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Delete Portfolio</DialogTitle>
              </DialogHeader>
              <p className="text-sm text-muted-foreground mt-2">
                Are you sure you want to delete this portfolio? This action
                cannot be undone. All trades and holdings data will be
                permanently removed.
              </p>
              <div className="flex gap-2 mt-4 justify-end">
                <Button
                  variant="outline"
                  onClick={() => setDeleteDialogOpen(false)}
                >
                  Cancel
                </Button>
                <Button
                  variant="destructive"
                  onClick={() => deleteMutation.mutate(activeId)}
                  disabled={deleteMutation.isPending}
                >
                  {deleteMutation.isPending ? "Deleting..." : "Delete"}
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        )}
      </div>

      {/* Summary Cards */}
      {activeId && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
            {detailLoading ? (
              Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-24 w-full" />
              ))
            ) : portfolio ? (
              <>
                <MetricCard
                  title="Total Value"
                  value={formatCurrency(portfolio.total_value ?? 0)}
                  icon={<Briefcase className="h-4 w-4" />}
                />
                <MetricCard
                  title="Total Cost"
                  value={formatCurrency(portfolio.total_cost ?? 0)}
                  icon={<DollarSign className="h-4 w-4" />}
                />
                <MetricCard
                  title="Total Gain/Loss"
                  value={formatCurrency(portfolio.total_gain ?? 0)}
                  changePct={totalGainPct ?? undefined}
                  icon={<TrendingUp className="h-4 w-4" />}
                />
                <MetricCard
                  title="Holdings"
                  value={holdings.length.toString()}
                />
              </>
            ) : null}
          </div>

          <Separator />

          {/* Holdings Table */}
          <div>
            <h2 className="text-xl font-semibold mb-4">Holdings</h2>
            {detailLoading ? (
              <div className="space-y-2">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Skeleton key={i} className="h-10 w-full" />
                ))}
              </div>
            ) : holdings.length > 0 ? (
              <DataTable data={holdings} columns={holdingsColumns} />
            ) : (
              <Card>
                <CardContent className="py-8 text-center text-muted-foreground">
                  No holdings. Add trades to get started.
                </CardContent>
              </Card>
            )}
          </div>

          <Separator />

          {/* Allocation Charts */}
          <div>
            <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
              <BarChart3 className="h-5 w-5" />
              Asset Allocation
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">By Stock</CardTitle>
                </CardHeader>
                <CardContent>
                  <ChartContainer
                    isLoading={allocLoading}
                    isEmpty={!allocation || allocation.by_stock.length === 0}
                    height="h-64"
                  >
                    <AllocationChart
                      data={allocation?.by_stock ?? []}
                      title="By Stock"
                    />
                  </ChartContainer>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">By Sector</CardTitle>
                </CardHeader>
                <CardContent>
                  <ChartContainer
                    isLoading={allocLoading}
                    isEmpty={!allocation || allocation.by_sector.length === 0}
                    height="h-64"
                  >
                    <AllocationChart
                      data={allocation?.by_sector ?? []}
                      title="By Sector"
                    />
                  </ChartContainer>
                </CardContent>
              </Card>
            </div>
          </div>

          <Separator />

          {/* Performance Chart */}
          <div>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold flex items-center gap-2">
                <TrendingUp className="h-5 w-5" />
                Performance
              </h2>
              <div className="flex gap-1">
                {PERF_PERIODS.map((p) => (
                  <Button
                    key={p.value}
                    variant={perfPeriod === p.value ? "default" : "outline"}
                    size="sm"
                    className="h-7 px-2 text-xs"
                    onClick={() => setPerfPeriod(p.value)}
                  >
                    {p.label}
                  </Button>
                ))}
              </div>
            </div>

            {performance && (
              <div className="flex gap-4 mb-4">
                <div className="text-sm">
                  <span className="text-muted-foreground">Portfolio Return: </span>
                  <span
                    className={
                      performance.total_return >= 0
                        ? "text-green-600 font-medium"
                        : "text-red-600 font-medium"
                    }
                  >
                    {performance.total_return >= 0 ? "+" : ""}
                    {performance.total_return.toFixed(2)}%
                  </span>
                </div>
                <div className="text-sm">
                  <span className="text-muted-foreground">Benchmark: </span>
                  <span
                    className={
                      performance.benchmark_return >= 0
                        ? "text-green-600 font-medium"
                        : "text-red-600 font-medium"
                    }
                  >
                    {performance.benchmark_return >= 0 ? "+" : ""}
                    {performance.benchmark_return.toFixed(2)}%
                  </span>
                </div>
              </div>
            )}

            <Card>
              <CardContent className="pt-4">
                <ChartContainer
                  isLoading={perfLoading}
                  isEmpty={
                    !performance || performance.data_points.length === 0
                  }
                  height="h-72"
                >
                  <PerformanceChart
                    data={performance?.data_points ?? []}
                  />
                </ChartContainer>
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </div>
  );
};

export default Portfolio;
