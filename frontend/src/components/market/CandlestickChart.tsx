import { useRef, useEffect, useState, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  createChart,
  CandlestickSeries,
  HistogramSeries,
  CrosshairMode,
  ColorType,
} from "lightweight-charts";
import type {
  IChartApi,
  ISeriesApi,
  MouseEventParams,
  Time,
  CandlestickData,
  HistogramData,
} from "lightweight-charts";
import { getChartData } from "@/api/market";
import type { ChartDataPoint, Period } from "@/types";

interface CandlestickChartProps {
  ticker: string;
  period?: Period;
  height?: number;
}

interface OhlcvLegend {
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  date: string;
}

const formatVolume = (vol: number): string => {
  if (vol >= 1_000_000_000) return `${(vol / 1_000_000_000).toFixed(2)}B`;
  if (vol >= 1_000_000) return `${(vol / 1_000_000).toFixed(2)}M`;
  if (vol >= 1_000) return `${(vol / 1_000).toFixed(1)}K`;
  return vol.toString();
};

const CandlestickChart = ({
  ticker,
  period = "1y",
  height = 400,
}: CandlestickChartProps) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candlestickSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const [legend, setLegend] = useState<OhlcvLegend | null>(null);

  // Always fetch max data — period only controls visible range
  const {
    data: chartData,
    isLoading,
    error,
  } = useQuery<ChartDataPoint[]>({
    queryKey: ["candlestickChart", ticker, "max"],
    queryFn: () => getChartData(ticker, "5y", "1d"),
    enabled: !!ticker,
    staleTime: 5 * 60_000,
  });

  const handleCrosshairMove = useCallback(
    (param: MouseEventParams<Time>) => {
      if (!param.time || !candlestickSeriesRef.current || !volumeSeriesRef.current) {
        setLegend(null);
        return;
      }

      const candleData = param.seriesData.get(candlestickSeriesRef.current) as
        | CandlestickData<Time>
        | undefined;
      const volumeData = param.seriesData.get(volumeSeriesRef.current) as
        | HistogramData<Time>
        | undefined;

      if (candleData && "open" in candleData) {
        setLegend({
          open: candleData.open,
          high: candleData.high,
          low: candleData.low,
          close: candleData.close,
          volume: volumeData?.value ?? 0,
          date: param.time as string,
        });
      }
    },
    [],
  );

  // Initialize chart
  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height,
      layout: {
        background: { type: ColorType.Solid, color: "#1a1a2e" },
        textColor: "#d1d5db",
        fontFamily: "'Geist Variable', system-ui, sans-serif",
      },
      grid: {
        vertLines: { color: "rgba(255, 255, 255, 0.06)" },
        horzLines: { color: "rgba(255, 255, 255, 0.06)" },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: {
          labelBackgroundColor: "#3b3b5c",
        },
        horzLine: {
          labelBackgroundColor: "#3b3b5c",
        },
      },
      rightPriceScale: {
        borderColor: "rgba(255, 255, 255, 0.1)",
        scaleMargins: {
          top: 0.1,
          bottom: 0.25,
        },
      },
      timeScale: {
        borderColor: "rgba(255, 255, 255, 0.1)",
        timeVisible: false,
        secondsVisible: false,
      },
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderDownColor: "#ef4444",
      borderUpColor: "#22c55e",
      wickDownColor: "#ef4444",
      wickUpColor: "#22c55e",
    });

    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: {
        type: "volume",
      },
      priceScaleId: "volume",
    });

    chart.priceScale("volume").applyOptions({
      scaleMargins: {
        top: 0.8,
        bottom: 0,
      },
    });

    chartRef.current = chart;
    candlestickSeriesRef.current = candleSeries;
    volumeSeriesRef.current = volumeSeries;

    chart.subscribeCrosshairMove(handleCrosshairMove);

    // Responsive resize
    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width } = entry.contentRect;
        chart.applyOptions({ width });
      }
    });
    resizeObserver.observe(chartContainerRef.current);

    return () => {
      chart.unsubscribeCrosshairMove(handleCrosshairMove);
      resizeObserver.disconnect();
      chart.remove();
      chartRef.current = null;
      candlestickSeriesRef.current = null;
      volumeSeriesRef.current = null;
    };
  }, [height, handleCrosshairMove, period]);

  // Update chart data when chartData changes
  useEffect(() => {
    if (
      !chartData ||
      chartData.length === 0 ||
      !candlestickSeriesRef.current ||
      !volumeSeriesRef.current
    )
      return;

    const candleData: CandlestickData<Time>[] = chartData.map((d) => ({
      time: d.date as Time,
      open: d.open,
      high: d.high,
      low: d.low,
      close: d.close,
    }));

    const volumeData: HistogramData<Time>[] = chartData.map((d) => ({
      time: d.date as Time,
      value: d.volume,
      color:
        d.close >= d.open
          ? "rgba(34, 197, 94, 0.4)"
          : "rgba(239, 68, 68, 0.4)",
    }));

    candlestickSeriesRef.current.setData(candleData);
    volumeSeriesRef.current.setData(volumeData);

    // Set the last data point as legend default
    const last = chartData[chartData.length - 1];
    if (last) {
      setLegend({
        open: last.open,
        high: last.high,
        low: last.low,
        close: last.close,
        volume: last.volume,
        date: last.date,
      });
    }

    // Set initial visible range based on period
    if (chartRef.current && chartData.length > 0) {
      const periodDays: Record<string, number> = {
        "1d": 1, "1w": 5, "1m": 22, "3m": 66, "6m": 132, "1y": 252, "5y": 1260,
      };
      const days = periodDays[period] ?? chartData.length;
      const fromIndex = Math.max(0, chartData.length - days);
      const from = chartData[fromIndex].date as Time;
      const to = chartData[chartData.length - 1].date as Time;
      chartRef.current.timeScale().setVisibleRange({ from, to });
    }
  }, [chartData, period]);

  return (
    <div className="relative" style={{ height }}>
      {/* Loading / Error overlays */}
      {isLoading && (
        <div className="absolute inset-0 flex items-center justify-center z-20 bg-background/80">
          <p className="text-muted-foreground text-sm animate-pulse">Loading chart...</p>
        </div>
      )}
      {error && (
        <div className="absolute inset-0 flex items-center justify-center z-20 bg-destructive/5">
          <p className="text-destructive text-sm">Failed to load chart</p>
        </div>
      )}

      {/* OHLCV Legend Overlay */}
      {legend && !isLoading && (
        <div className="absolute top-2 left-3 z-10 flex items-center gap-3 text-xs font-mono">
          <span className="text-gray-400">{legend.date}</span>
          <span className="text-gray-400">
            O <span className="text-white font-medium">{legend.open.toFixed(2)}</span>
          </span>
          <span className="text-gray-400">
            H <span className="text-white font-medium">{legend.high.toFixed(2)}</span>
          </span>
          <span className="text-gray-400">
            L <span className="text-white font-medium">{legend.low.toFixed(2)}</span>
          </span>
          <span className="text-gray-400">
            C{" "}
            <span className={legend.close >= legend.open ? "text-green-400 font-medium" : "text-red-400 font-medium"}>
              {legend.close.toFixed(2)}
            </span>
          </span>
          <span className="text-gray-400">
            Vol <span className="text-white font-medium">{formatVolume(legend.volume)}</span>
          </span>
        </div>
      )}

      {/* Chart container — always rendered so ref is always available */}
      <div ref={chartContainerRef} style={{ height }} />
    </div>
  );
};

export default CandlestickChart;
