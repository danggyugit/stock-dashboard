import apiClient from "./client";
import type {
  Portfolio,
  Trade,
  TradeCreate,
  AllocationResponse,
  PerformanceResponse,
  DividendSummary,
  TaxSummary,
  Period,
} from "@/types";

export const getPortfolios = async (): Promise<Portfolio[]> => {
  const { data } = await apiClient.get<Portfolio[]>("/portfolio");
  return data;
};

export const createPortfolio = async (payload: {
  name: string;
  description?: string;
}): Promise<Portfolio> => {
  const { data } = await apiClient.post<Portfolio>("/portfolio", payload);
  return data;
};

export const getPortfolioDetail = async (id: number): Promise<Portfolio> => {
  const { data } = await apiClient.get<Portfolio>(`/portfolio/${id}`);
  return data;
};

export const deletePortfolio = async (id: number): Promise<void> => {
  await apiClient.delete(`/portfolio/${id}`);
};

interface TradesResponse {
  trades: Trade[];
  total: number;
  page: number;
  page_size: number;
}

export const getTrades = async (id: number, page = 1): Promise<TradesResponse> => {
  const { data } = await apiClient.get<TradesResponse>(`/portfolio/${id}/trades`, {
    params: { page },
  });
  return data;
};

export const addTrade = async (id: number, trade: TradeCreate): Promise<Trade> => {
  const { data } = await apiClient.post<Trade>(`/portfolio/${id}/trades`, trade);
  return data;
};

export const deleteTrade = async (id: number, tid: number): Promise<void> => {
  await apiClient.delete(`/portfolio/${id}/trades/${tid}`);
};

export const importTrades = async (id: number, file: File): Promise<{ imported: number }> => {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await apiClient.post<{ imported: number }>(
    `/portfolio/${id}/trades/import`,
    formData,
    { headers: { "Content-Type": "multipart/form-data" } },
  );
  return data;
};

export const getAllocation = async (id: number): Promise<AllocationResponse> => {
  const { data } = await apiClient.get<AllocationResponse>(`/portfolio/${id}/allocation`);
  return data;
};

export const getPerformance = async (
  id: number,
  period: Period = "1m",
): Promise<PerformanceResponse> => {
  const { data } = await apiClient.get<PerformanceResponse>(`/portfolio/${id}/performance`, {
    params: { period },
  });
  return data;
};

export const getDividends = async (id: number, year?: number): Promise<DividendSummary> => {
  const { data } = await apiClient.get<DividendSummary>(`/portfolio/${id}/dividends`, {
    params: { year },
  });
  return data;
};

export const getTax = async (id: number, year?: number): Promise<TaxSummary> => {
  const { data } = await apiClient.get<TaxSummary>(`/portfolio/${id}/tax`, {
    params: { year },
  });
  return data;
};
