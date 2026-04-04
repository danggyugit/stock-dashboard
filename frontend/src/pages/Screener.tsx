import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import type { ColumnDef } from "@tanstack/react-table";
import { Filter, RotateCcw } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import DataTable from "@/components/common/DataTable";
import PriceChange from "@/components/common/PriceChange";
import { getScreenerResults } from "@/api/market";
import { formatCurrency, formatNumber } from "@/lib/utils";
import type { ScreenerParams, ScreenerResult, ScreenerResponse } from "@/types";

const GICS_SECTORS = [
  "All",
  "Information Technology",
  "Health Care",
  "Financials",
  "Consumer Discretionary",
  "Communication Services",
  "Industrials",
  "Consumer Staples",
  "Energy",
  "Utilities",
  "Real Estate",
  "Materials",
];

interface MarketCapPreset {
  label: string;
  min?: number;
  max?: number;
}

const MARKET_CAP_PRESETS: MarketCapPreset[] = [
  { label: "All", min: undefined, max: undefined },
  { label: "Mega (>200B)", min: 200_000_000_000, max: undefined },
  { label: "Large (10-200B)", min: 10_000_000_000, max: 200_000_000_000 },
  { label: "Mid (2-10B)", min: 2_000_000_000, max: 10_000_000_000 },
  { label: "Small (<2B)", min: undefined, max: 2_000_000_000 },
];

const defaultFilters: ScreenerParams = {
  page: 1,
  page_size: 50,
};

const Screener = () => {
  const navigate = useNavigate();
  const [filters, setFilters] = useState<ScreenerParams>(defaultFilters);
  const [capPreset, setCapPreset] = useState("All");
  const [minPe, setMinPe] = useState("");
  const [maxPe, setMaxPe] = useState("");
  const [minDividend, setMinDividend] = useState("");
  const [minCapCustom, setMinCapCustom] = useState("");
  const [maxCapCustom, setMaxCapCustom] = useState("");

  const { data, isLoading, error } = useQuery<ScreenerResponse>({
    queryKey: ["screener", filters],
    queryFn: () => getScreenerResults(filters),
    staleTime: 2 * 60_000,
  });

  const updateFilter = (
    updates: Partial<ScreenerParams>,
  ) => {
    setFilters((prev) => ({
      ...prev,
      ...updates,
      page: 1,
    }));
  };

  const handleCapPreset = (label: string) => {
    setCapPreset(label);
    setMinCapCustom("");
    setMaxCapCustom("");
    const preset = MARKET_CAP_PRESETS.find((p) => p.label === label);
    if (preset) {
      updateFilter({ min_cap: preset.min, max_cap: preset.max });
    }
  };

  const handleReset = () => {
    setFilters(defaultFilters);
    setCapPreset("All");
    setMinPe("");
    setMaxPe("");
    setMinDividend("");
    setMinCapCustom("");
    setMaxCapCustom("");
  };

  const columns: ColumnDef<ScreenerResult, unknown>[] = [
    {
      accessorKey: "ticker",
      header: "Ticker",
      cell: ({ row }) => (
        <span className="font-medium">{row.original.ticker}</span>
      ),
    },
    {
      accessorKey: "name",
      header: "Name",
      cell: ({ row }) => (
        <span className="text-sm truncate max-w-[200px] block">
          {row.original.name}
        </span>
      ),
    },
    {
      accessorKey: "price",
      header: "Price",
      cell: ({ row }) => formatCurrency(row.original.price),
    },
    {
      accessorKey: "change_pct",
      header: "Change",
      cell: ({ row }) => <PriceChange percent={row.original.change_pct} />,
    },
    {
      accessorKey: "market_cap",
      header: "Market Cap",
      cell: ({ row }) => formatNumber(row.original.market_cap),
    },
    {
      accessorKey: "pe_ratio",
      header: "P/E",
      cell: ({ row }) =>
        row.original.pe_ratio != null
          ? row.original.pe_ratio.toFixed(2)
          : "--",
    },
    {
      accessorKey: "dividend_yield",
      header: "Div Yield",
      cell: ({ row }) =>
        row.original.dividend_yield != null
          ? `${(row.original.dividend_yield * 100).toFixed(2)}%`
          : "--",
    },
    {
      accessorKey: "volume",
      header: "Volume",
      cell: ({ row }) => formatNumber(row.original.volume),
    },
  ];

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Stock Screener</h1>
        <p className="text-muted-foreground">
          Filter and find stocks matching your criteria.
        </p>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Filter className="h-4 w-4" />
            Filters
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Row 1: Sector, Market Cap Presets */}
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {/* Sector */}
            <div className="space-y-1.5">
              <Label className="text-xs">Sector</Label>
              <Select
                value={filters.sector ?? "All"}
                onValueChange={(v: string | null) =>
                  updateFilter({ sector: !v || v === "All" ? undefined : v })
                }
              >
                <SelectTrigger className="h-9">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {GICS_SECTORS.map((s) => (
                    <SelectItem key={s} value={s}>
                      {s}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Market Cap Preset */}
            <div className="space-y-1.5 sm:col-span-2 lg:col-span-3">
              <Label className="text-xs">Market Cap</Label>
              <div className="flex flex-wrap gap-2">
                {MARKET_CAP_PRESETS.map((preset) => (
                  <Button
                    key={preset.label}
                    variant={capPreset === preset.label ? "default" : "outline"}
                    size="sm"
                    className="h-9 text-xs"
                    onClick={() => handleCapPreset(preset.label)}
                  >
                    {preset.label}
                  </Button>
                ))}
              </div>
            </div>
          </div>

          {/* Row 2: Custom Market Cap, P/E, Dividend, Sort */}
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            {/* Min Market Cap Custom */}
            <div className="space-y-1.5">
              <Label className="text-xs">Min Cap ($B)</Label>
              <Input
                type="number"
                placeholder="0"
                className="h-9"
                value={minCapCustom}
                onChange={(e) => {
                  setMinCapCustom(e.target.value);
                  setCapPreset("All");
                  updateFilter({
                    min_cap: e.target.value
                      ? Number(e.target.value) * 1_000_000_000
                      : undefined,
                  });
                }}
              />
            </div>

            {/* Max Market Cap Custom */}
            <div className="space-y-1.5">
              <Label className="text-xs">Max Cap ($B)</Label>
              <Input
                type="number"
                placeholder="Any"
                className="h-9"
                value={maxCapCustom}
                onChange={(e) => {
                  setMaxCapCustom(e.target.value);
                  setCapPreset("All");
                  updateFilter({
                    max_cap: e.target.value
                      ? Number(e.target.value) * 1_000_000_000
                      : undefined,
                  });
                }}
              />
            </div>

            {/* Min P/E */}
            <div className="space-y-1.5">
              <Label className="text-xs">Min P/E</Label>
              <Input
                type="number"
                placeholder="Any"
                className="h-9"
                value={minPe}
                onChange={(e) => {
                  setMinPe(e.target.value);
                  updateFilter({
                    min_pe: e.target.value
                      ? Number(e.target.value)
                      : undefined,
                  });
                }}
              />
            </div>

            {/* Max P/E */}
            <div className="space-y-1.5">
              <Label className="text-xs">Max P/E</Label>
              <Input
                type="number"
                placeholder="Any"
                className="h-9"
                value={maxPe}
                onChange={(e) => {
                  setMaxPe(e.target.value);
                  updateFilter({
                    max_pe: e.target.value
                      ? Number(e.target.value)
                      : undefined,
                  });
                }}
              />
            </div>

            {/* Min Dividend */}
            <div className="space-y-1.5">
              <Label className="text-xs">Min Div Yield (%)</Label>
              <Input
                type="number"
                placeholder="0"
                step="0.1"
                className="h-9"
                value={minDividend}
                onChange={(e) => {
                  setMinDividend(e.target.value);
                  updateFilter({
                    min_dividend: e.target.value
                      ? Number(e.target.value) / 100
                      : undefined,
                  });
                }}
              />
            </div>

            {/* Sort */}
            <div className="space-y-1.5">
              <Label className="text-xs">Sort By</Label>
              <Select
                value={filters.sort_by ?? "market_cap"}
                onValueChange={(v: string | null) => updateFilter({ sort_by: v ?? "market_cap" })}
              >
                <SelectTrigger className="h-9">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="market_cap">Market Cap</SelectItem>
                  <SelectItem value="change_pct">Change %</SelectItem>
                  <SelectItem value="pe_ratio">P/E Ratio</SelectItem>
                  <SelectItem value="dividend_yield">Dividend</SelectItem>
                  <SelectItem value="volume">Volume</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Reset button */}
          <div className="flex justify-end">
            <Button
              variant="outline"
              size="sm"
              className="h-9 gap-1.5"
              onClick={handleReset}
            >
              <RotateCcw className="h-3.5 w-3.5" />
              Reset Filters
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Results */}
      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 10 }).map((_, i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </div>
      ) : error ? (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            Failed to load screener results. Backend may not be running.
          </CardContent>
        </Card>
      ) : (
        <div>
          {data && (
            <p className="text-sm text-muted-foreground mb-2">
              <span className="font-medium text-foreground">{data.total}</span>{" "}
              stocks found
              {data.total > data.page_size && (
                <span className="ml-1">
                  (page {data.page} of {Math.ceil(data.total / data.page_size)})
                </span>
              )}
            </p>
          )}
          <DataTable
            data={data?.results ?? []}
            columns={columns}
            pageSize={50}
            onRowClick={(row) => navigate(`/stock/${row.ticker}`)}
          />
        </div>
      )}
    </div>
  );
};

export default Screener;
