import { useState, useRef, useEffect, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { ArrowLeft, Plus, Trash2, Upload, Loader2 } from "lucide-react";
import type { ColumnDef } from "@tanstack/react-table";
import { Card, CardContent } from "@/components/ui/card";
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

} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import DataTable from "@/components/common/DataTable";
import TickerSearch from "@/components/common/TickerSearch";
import {
  getPortfolios,
  getTrades,
  addTrade,
  deleteTrade,
  importTrades,
} from "@/api/portfolio";
import { getClosePrice } from "@/api/market";
import { formatCurrency, formatDate } from "@/lib/utils";
import type { Portfolio, Trade, TradeCreate } from "@/types";

const Trades = () => {
  const queryClient = useQueryClient();
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<number | null>(
    null,
  );
  const [dialogOpen, setDialogOpen] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [tradeForm, setTradeForm] = useState<TradeCreate>({
    ticker: "",
    trade_type: "BUY",
    quantity: 0,
    price: 0,
    commission: 0,
    trade_date: new Date().toISOString().split("T")[0],
    note: "",
  });
  const [priceLoading, setPriceLoading] = useState(false);
  const [priceAutoFilled, setPriceAutoFilled] = useState(false);

  // Auto-fetch close price when ticker + date are set
  const fetchClosePrice = useCallback(async (ticker: string, date: string) => {
    if (!ticker || !date) return;
    setPriceLoading(true);
    try {
      const result = await getClosePrice(ticker, date);
      if (result.close != null) {
        setTradeForm((f) => ({ ...f, price: result.close! }));
        setPriceAutoFilled(true);
      }
    } catch {
      // ignore - user can enter manually
    } finally {
      setPriceLoading(false);
    }
  }, []);

  // Trigger price fetch when ticker or date changes
  useEffect(() => {
    if (tradeForm.ticker && tradeForm.trade_date) {
      setPriceAutoFilled(false);
      fetchClosePrice(tradeForm.ticker, tradeForm.trade_date);
    }
  }, [tradeForm.ticker, tradeForm.trade_date, fetchClosePrice]);

  const { data: portfolios, isLoading: portfoliosLoading } = useQuery<
    Portfolio[]
  >({
    queryKey: ["portfolios"],
    queryFn: getPortfolios,
    staleTime: 60_000,
  });

  const activeId = selectedPortfolioId ?? portfolios?.[0]?.id ?? null;

  const { data: tradesResponse, isLoading: tradesLoading } = useQuery({
    queryKey: ["trades", activeId],
    queryFn: () => getTrades(activeId!),
    enabled: activeId !== null,
    staleTime: 30_000,
  });
  const trades = tradesResponse?.trades;

  const addMutation = useMutation({
    mutationFn: () => addTrade(activeId!, tradeForm),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["trades", activeId] });
      queryClient.invalidateQueries({
        queryKey: ["portfolioDetail", activeId],
      });
      queryClient.invalidateQueries({ queryKey: ["allocation", activeId] });
      setDialogOpen(false);
      setTradeForm({
        ticker: "",
        trade_type: "BUY",
        quantity: 0,
        price: 0,
        commission: 0,
        trade_date: new Date().toISOString().split("T")[0],
        note: "",
      });
    },
  });

  const deleteTradeM = useMutation({
    mutationFn: (tid: number) => deleteTrade(activeId!, tid),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["trades", activeId] });
      queryClient.invalidateQueries({
        queryKey: ["portfolioDetail", activeId],
      });
      queryClient.invalidateQueries({ queryKey: ["allocation", activeId] });
    },
  });

  const importMutation = useMutation({
    mutationFn: (file: File) => importTrades(activeId!, file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["trades", activeId] });
      queryClient.invalidateQueries({
        queryKey: ["portfolioDetail", activeId],
      });
    },
  });

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      importMutation.mutate(file);
      e.target.value = "";
    }
  };

  const columns: ColumnDef<Trade, unknown>[] = [
    {
      accessorKey: "trade_date",
      header: "Date",
      cell: ({ row }) => formatDate(row.original.trade_date),
    },
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
            row.original.trade_type === "BUY" ? "default" : "destructive"
          }
          className={
            row.original.trade_type === "BUY"
              ? "bg-blue-600 hover:bg-blue-700"
              : ""
          }
        >
          {row.original.trade_type}
        </Badge>
      ),
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
      id: "total",
      header: "Total",
      cell: ({ row }) =>
        formatCurrency(row.original.quantity * row.original.price),
    },
    {
      accessorKey: "commission",
      header: "Commission",
      cell: ({ row }) => formatCurrency(row.original.commission),
    },
    {
      accessorKey: "note",
      header: "Note",
      cell: ({ row }) => (
        <span className="text-xs text-muted-foreground truncate max-w-[120px] block">
          {row.original.note || "--"}
        </span>
      ),
    },
    {
      id: "actions",
      header: "",
      cell: ({ row }) => (
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7 text-destructive"
          onClick={(e) => {
            e.stopPropagation();
            if (window.confirm("Delete this trade?")) {
              deleteTradeM.mutate(row.original.id);
            }
          }}
        >
          <Trash2 className="h-3 w-3" />
        </Button>
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
        <h1 className="text-3xl font-bold tracking-tight">Trade History</h1>
        <p className="text-muted-foreground">
          View, add, and manage your trades.
        </p>
      </div>

      {/* Portfolio Selector + Add Trade + CSV Import */}
      <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center">
        {portfoliosLoading ? (
          <Skeleton className="h-9 w-48" />
        ) : portfolios && portfolios.length > 0 ? (
          <Select
            value={activeId?.toString() ?? ""}
            onValueChange={(v) => setSelectedPortfolioId(Number(v))}
          >
            <SelectTrigger className="w-56">
              <span>{portfolios.find((p) => p.id === activeId)?.name ?? "Select portfolio"}</span>
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

        {activeId && (
          <>
            <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
              <DialogTrigger render={<Button size="sm" />}>
                <Plus className="h-4 w-4 mr-1" />
                Add Trade
              </DialogTrigger>
              <DialogContent className="max-w-md">
                <DialogHeader>
                  <DialogTitle>Add Trade</DialogTitle>
                </DialogHeader>
                <div className="space-y-3 mt-2">
                  {/* Row 1: Type + Ticker */}
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-1.5">
                      <Label>Type</Label>
                      <Select
                        value={tradeForm.trade_type}
                        onValueChange={(v) =>
                          setTradeForm((f) => ({
                            ...f,
                            trade_type: v as "BUY" | "SELL",
                          }))
                        }
                      >
                        <SelectTrigger>
                          <span>{tradeForm.trade_type === "BUY" ? "Buy" : "Sell"}</span>
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="BUY">Buy</SelectItem>
                          <SelectItem value="SELL">Sell</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-1.5">
                      <Label>Ticker</Label>
                      <TickerSearch
                        onSelect={(ticker) =>
                          setTradeForm((f) => ({ ...f, ticker }))
                        }
                        placeholder="Search ticker..."
                      />
                      {tradeForm.ticker && (
                        <p className="text-xs text-muted-foreground">
                          Selected: <span className="font-medium">{tradeForm.ticker}</span>
                        </p>
                      )}
                    </div>
                  </div>

                  {/* Row 2: Date + Price */}
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-1.5">
                      <Label>Date</Label>
                      <Input
                        type="date"
                        value={tradeForm.trade_date}
                        onChange={(e) =>
                          setTradeForm((f) => ({
                            ...f,
                            trade_date: e.target.value,
                          }))
                        }
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label className="flex items-center gap-1.5">
                        Price ($)
                        {priceLoading && <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />}
                        {priceAutoFilled && !priceLoading && (
                          <span className="text-[10px] text-green-600 font-normal">auto</span>
                        )}
                      </Label>
                      <Input
                        type="number"
                        step="0.01"
                        value={tradeForm.price || ""}
                        onChange={(e) => {
                          setPriceAutoFilled(false);
                          setTradeForm((f) => ({
                            ...f,
                            price: Number(e.target.value),
                          }));
                        }}
                        placeholder={priceLoading ? "Loading..." : "0.00"}
                      />
                    </div>
                  </div>

                  {/* Row 3: Quantity + Commission */}
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-1.5">
                      <Label>Quantity</Label>
                      <Input
                        type="number"
                        value={tradeForm.quantity || ""}
                        onChange={(e) =>
                          setTradeForm((f) => ({
                            ...f,
                            quantity: Number(e.target.value),
                          }))
                        }
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label>Commission ($)</Label>
                      <Input
                        type="number"
                        step="0.01"
                        value={tradeForm.commission || ""}
                        onChange={(e) =>
                          setTradeForm((f) => ({
                            ...f,
                            commission: Number(e.target.value),
                          }))
                        }
                      />
                    </div>
                  </div>

                  {/* Row 4: Note */}
                  <div className="space-y-1.5">
                    <Label>Note (optional)</Label>
                    <Input
                      value={tradeForm.note ?? ""}
                      onChange={(e) =>
                        setTradeForm((f) => ({ ...f, note: e.target.value }))
                      }
                      placeholder="e.g. earnings play"
                    />
                  </div>

                  {/* Total preview */}
                  {tradeForm.price > 0 && tradeForm.quantity > 0 && (
                    <div className="rounded-md bg-muted/50 px-3 py-2 text-sm flex justify-between">
                      <span className="text-muted-foreground">Total</span>
                      <span className="font-semibold">
                        {formatCurrency(tradeForm.price * tradeForm.quantity + (tradeForm.commission ?? 0))}
                      </span>
                    </div>
                  )}

                  <Button
                    onClick={() => addMutation.mutate()}
                    disabled={
                      !tradeForm.ticker ||
                      tradeForm.quantity <= 0 ||
                      tradeForm.price <= 0 ||
                      addMutation.isPending
                    }
                    className="w-full"
                  >
                    {addMutation.isPending ? "Adding..." : "Add Trade"}
                  </Button>
                </div>
              </DialogContent>
            </Dialog>

            <input
              ref={fileInputRef}
              type="file"
              accept=".csv"
              className="hidden"
              onChange={handleFileChange}
            />
            <Button
              variant="outline"
              size="sm"
              onClick={() => fileInputRef.current?.click()}
              disabled={importMutation.isPending}
            >
              <Upload className="h-4 w-4 mr-1" />
              {importMutation.isPending ? "Importing..." : "Import CSV"}
            </Button>
          </>
        )}
      </div>

      {/* Trades Table */}
      {activeId &&
        (tradesLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 10 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : trades && trades.length > 0 ? (
          <DataTable data={trades} columns={columns} pageSize={20} />
        ) : (
          <Card>
            <CardContent className="py-8 text-center text-muted-foreground">
              No trades yet. Click &quot;Add Trade&quot; to get started.
            </CardContent>
          </Card>
        ))}
    </div>
  );
};

export default Trades;
