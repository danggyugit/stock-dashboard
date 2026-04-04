import apiClient from "./client";
import type {
  HeatmapResponse,
  ScreenerParams,
  ScreenerResponse,
  IndexInfo,
  StockDetail,
  ChartDataPoint,
  CompareResponse,
  SearchResult,
  Period,
  ChartInterval,
} from "@/types";

export const getHeatmapData = async (period: Period = "1d"): Promise<HeatmapResponse> => {
  const { data } = await apiClient.get<HeatmapResponse>("/market/heatmap", {
    params: { period },
  });
  return data;
};

export const getScreenerResults = async (params: ScreenerParams): Promise<ScreenerResponse> => {
  const { data } = await apiClient.get<ScreenerResponse>("/market/screener", {
    params,
  });
  return data;
};

export const getIndices = async (): Promise<IndexInfo[]> => {
  const { data } = await apiClient.get<IndexInfo[]>("/market/indices");
  return data;
};

export const getStockDetail = async (ticker: string): Promise<StockDetail> => {
  const { data } = await apiClient.get<StockDetail>(`/market/stock/${ticker}`);
  return data;
};

export const getChartData = async (
  ticker: string,
  period: Period = "1y",
  interval: ChartInterval = "1d",
): Promise<ChartDataPoint[]> => {
  const { data } = await apiClient.get<ChartDataPoint[]>(`/market/stock/${ticker}/chart`, {
    params: { period, interval },
  });
  return data;
};

export const getFinancials = async (ticker: string): Promise<StockDetail> => {
  const { data } = await apiClient.get<StockDetail>(`/market/stock/${ticker}/financials`);
  return data;
};

export const getCompareData = async (
  tickers: string[],
  period: Period = "1y",
): Promise<CompareResponse> => {
  const { data } = await apiClient.get<CompareResponse>("/market/compare", {
    params: { tickers: tickers.join(","), period },
  });
  return data;
};

export const searchStocks = async (query: string): Promise<SearchResult[]> => {
  const { data } = await apiClient.get<SearchResult[]>("/market/search", {
    params: { q: query },
  });
  return data;
};

export const getClosePrice = async (
  ticker: string,
  date: string,
): Promise<{ ticker: string; date: string; close: number | null }> => {
  const { data } = await apiClient.get(`/market/stock/${ticker}/close`, {
    params: { date },
  });
  return data;
};

export const refreshMarketData = async (): Promise<{ message: string }> => {
  const { data } = await apiClient.post<{ message: string }>("/market/refresh");
  return data;
};
