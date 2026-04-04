import apiClient from "./client";
import type {
  FearGreedData,
  FearGreedHistory,
  NewsResponse,
  SentimentTrend,
  DailyReport,
} from "@/types";

export const getFearGreed = async (): Promise<FearGreedData> => {
  const { data } = await apiClient.get<FearGreedData>("/sentiment/fear-greed");
  return data;
};

export const getFearGreedHistory = async (
  days = 30,
): Promise<FearGreedHistory> => {
  const { data } = await apiClient.get<FearGreedHistory>(
    "/sentiment/fear-greed/history",
    { params: { days } },
  );
  return data;
};

export const getNews = async (
  ticker?: string,
  page = 1,
): Promise<NewsResponse> => {
  const { data } = await apiClient.get<NewsResponse>("/sentiment/news", {
    params: { ticker, page },
  });
  return data;
};

export const analyzeSentiment = async (
  ticker?: string,
): Promise<{ status: string; analyzed: number }> => {
  const { data } = await apiClient.post<{ status: string; analyzed: number }>(
    "/sentiment/analyze",
    null,
    { params: { ticker } },
  );
  return data;
};

export const getSentimentTrend = async (
  ticker: string,
  days = 30,
): Promise<SentimentTrend> => {
  const { data } = await apiClient.get<SentimentTrend>(
    `/sentiment/trend/${ticker}`,
    { params: { days } },
  );
  return data;
};

export const getDailyReport = async (): Promise<DailyReport | null> => {
  try {
    const { data } = await apiClient.get<DailyReport>("/sentiment/report");
    if (data && data.content) {
      return data;
    }
    return null;
  } catch (err: unknown) {
    const axiosErr = err as { response?: { status?: number } };
    if (axiosErr.response?.status === 404) {
      return null;
    }
    throw err;
  }
};

export const generateReport = async (): Promise<{ status: string; message: string }> => {
  const { data } = await apiClient.post<{ status: string; message: string }>(
    "/sentiment/report/generate",
  );
  return data;
};
