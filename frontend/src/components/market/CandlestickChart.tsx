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

  const {
    data: chartData,
    isLoading,
    error,
  } = useQuery<ChartDataPoint[]>({
    queryKey: ["candlestickChart", ticker, period],
    queryFn: () => getChartData(ticker, period),
    enabled: !!ticker,
    staleTime: 60_000,
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
        timeVisible: period === "1d",
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

    chartRef.current?.timeScale().fitContent();
  }, [chartData]);

  if (error) {
    return (
      <div
        className="flex items-center justify-center rounded-md bg-destructive/5 border border-destructive/20"
        style={{ height }}
      >
        <p className="text-destructive text-sm">
          Failed to load chart data: {(error as Error).message}
        </p>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div
        className="flex items-center justify-center rounded-md bg-muted/30 animate-pulse"
        style={{ height }}
      >
        <p className="text-muted-foreground text-sm">Loading chart...</p>
      </div>
    );
  }

  return (
    <div className="relative">
      {/* OHLCV Legend Overlay */}
      {legend && (
        <div className="absolute top-2 left-3 z-10 flex items-center gap-3 text-xs font-mono">
          <span className="text-gray-400">{legend.date}</span>
          <span className="text-gray-400">
            O{" "}
            <span className="text-white font-medium">
              {legend.open.toFixed(2)}
            </span>
          </span>
          <span className="text-gray-400">
            H{" "}
            <span className="text-white font-medium">
              {legend.high.toFixed(2)}
            </span>
          </span>
          <span className="text-gray-400">
            L{" "}
            <span className="text-white font-medium">
              {legend.low.toFixed(2)}
            </span>
          </span>
          <span className="text-gray-400">
            C{" "}
            <span
              className={
                legend.close >= legend.open
                  ? "text-green-400 font-medium"
                  : "text-red-400 font-medium"
              }
            >
              {legend.close.toFixed(2)}
            </span>
          </span>
          <span className="text-gray-400">
            Vol{" "}
            <span className="text-white font-medium">
              {formatVolume(legend.volume)}
            </span>
          </span>
        </div>
      )}
      <div ref={chartContainerRef} style={{ height }} />
    </div>
  );
};

export default CandlestickChart;
