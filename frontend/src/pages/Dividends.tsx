import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Calendar, DollarSign, ChevronLeft, ChevronRight } from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
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
import ChartContainer from "@/components/common/ChartContainer";
import DividendCalendar from "@/components/portfolio/DividendCalendar";
import { getPortfolios, getDividends } from "@/api/portfolio";
import { formatCurrency, formatDate } from "@/lib/utils";
import type { Portfolio, DividendSummary, DividendEvent } from "@/types";
import type { ColumnDef } from "@tanstack/react-table";

const currentYear = new Date().getFullYear();
const years = Array.from({ length: 5 }, (_, i) => currentYear - i);
const MONTH_NAMES = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

const Dividends = () => {
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<number | null>(
    null,
  );
  const [year, setYear] = useState(currentYear);
  const [calendarMonth, setCalendarMonth] = useState(new Date().getMonth() + 1);

  const { data: portfolios, isLoading: portfoliosLoading } = useQuery<
    Portfolio[]
  >({
    queryKey: ["portfolios"],
    queryFn: getPortfolios,
    staleTime: 60_000,
  });

  const activeId = selectedPortfolioId ?? portfolios?.[0]?.id ?? null;

  const { data: dividendData, isLoading: dividendsLoading } =
    useQuery<DividendSummary>({
      queryKey: ["dividends", activeId, year],
      queryFn: () => getDividends(activeId!, year),
      enabled: activeId !== null,
      staleTime: 5 * 60_000,
    });

  const monthlyChartData = MONTH_NAMES.map((month, idx) => {
    const monthKey = `${year}-${String(idx + 1).padStart(2, "0")}`;
    return {
      month,
      amount: dividendData?.monthly_breakdown?.[monthKey] ?? 0,
    };
  });

  const monthlyAvg =
    dividendData && dividendData.total_annual
      ? dividendData.total_annual / 12
      : 0;

  const columns: ColumnDef<DividendEvent, unknown>[] = [
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
      accessorKey: "name",
      header: "Name",
      cell: ({ row }) => (
        <span className="text-sm truncate max-w-[160px] block">
          {row.original.name}
        </span>
      ),
    },
    {
      accessorKey: "ex_date",
      header: "Ex-Date",
      cell: ({ row }) => formatDate(row.original.ex_date),
    },
    {
      accessorKey: "payment_date",
      header: "Payment Date",
      cell: ({ row }) =>
        row.original.payment_date
          ? formatDate(row.original.payment_date)
          : "--",
    },
    {
      accessorKey: "amount",
      header: "Per Share",
      cell: ({ row }) => formatCurrency(row.original.amount),
    },
    {
      accessorKey: "quantity",
      header: "Shares",
      cell: ({ row }) => row.original.quantity.toFixed(2),
    },
    {
      accessorKey: "total_amount",
      header: "Total",
      cell: ({ row }) => (
        <span className="font-medium text-green-600">
          {formatCurrency(row.original.total_amount)}
        </span>
      ),
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
        <h1 className="text-3xl font-bold tracking-tight">
          Dividend Calendar
        </h1>
        <p className="text-muted-foreground">
          Track dividend income from your holdings.
        </p>
      </div>

      {/* Controls */}
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

      {activeId && (
        <>
          {/* Summary */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <MetricCard
              title="Total Dividends (Annual)"
              value={
                dividendsLoading
                  ? "..."
                  : formatCurrency(dividendData?.total_annual ?? 0)
              }
              icon={<DollarSign className="h-4 w-4" />}
            />
            <MetricCard
              title="Monthly Average"
              value={dividendsLoading ? "..." : formatCurrency(monthlyAvg)}
              icon={<Calendar className="h-4 w-4" />}
            />
            <MetricCard
              title="Dividend Events"
              value={
                dividendsLoading
                  ? "..."
                  : (dividendData?.events.length ?? 0).toString()
              }
              icon={<Calendar className="h-4 w-4" />}
            />
          </div>

          {/* Calendar View */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">
                  Dividend Calendar - {MONTH_NAMES[calendarMonth - 1]} {year}
                </CardTitle>
                <div className="flex gap-1">
                  <Button
                    variant="outline"
                    size="icon"
                    className="h-7 w-7"
                    onClick={() =>
                      setCalendarMonth((m) => (m <= 1 ? 12 : m - 1))
                    }
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="outline"
                    size="icon"
                    className="h-7 w-7"
                    onClick={() =>
                      setCalendarMonth((m) => (m >= 12 ? 1 : m + 1))
                    }
                  >
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {dividendsLoading ? (
                <Skeleton className="h-64 w-full" />
              ) : (
                <DividendCalendar
                  events={dividendData?.events ?? []}
                  month={calendarMonth}
                  year={year}
                />
              )}
            </CardContent>
          </Card>

          {/* Monthly Bar Chart */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">
                Monthly Dividend Income ({year})
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ChartContainer
                isLoading={dividendsLoading}
                isEmpty={
                  !dividendData ||
                  Object.keys(dividendData.monthly_breakdown ?? {}).length === 0
                }
                height="h-64"
                emptyMessage="No dividend data for this year"
              >
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={monthlyChartData}
                    margin={{ top: 5, right: 20, left: 10, bottom: 5 }}
                  >
                    <CartesianGrid
                      strokeDasharray="3 3"
                      className="stroke-border"
                    />
                    <XAxis
                      dataKey="month"
                      tick={{ fontSize: 11 }}
                      className="text-muted-foreground"
                    />
                    <YAxis
                      tickFormatter={(v: number) => `$${v}`}
                      tick={{ fontSize: 11 }}
                      className="text-muted-foreground"
                    />
                    <Tooltip
                      formatter={(value) => [
                        formatCurrency(Number(value)),
                        "Dividends",
                      ]}
                      contentStyle={{
                        borderRadius: "6px",
                        fontSize: "12px",
                      }}
                    />
                    <Bar
                      dataKey="amount"
                      fill="#22C55E"
                      radius={[4, 4, 0, 0]}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </ChartContainer>
            </CardContent>
          </Card>

          {/* Events Table */}
          <div>
            <h2 className="text-xl font-semibold mb-4">Dividend Events</h2>
            {dividendsLoading ? (
              <div className="space-y-2">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Skeleton key={i} className="h-10 w-full" />
                ))}
              </div>
            ) : dividendData && dividendData.events.length > 0 ? (
              <DataTable data={dividendData.events} columns={columns} />
            ) : (
              <Card>
                <CardContent className="py-8 text-center text-muted-foreground">
                  No dividend events for {year}.
                </CardContent>
              </Card>
            )}
          </div>
        </>
      )}
    </div>
  );
};

export default Dividends;
