import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import { format } from "date-fns";

export const cn = (...inputs: ClassValue[]) => {
  return twMerge(clsx(inputs));
};

export const formatCurrency = (
  value: number | null | undefined,
  currency = "USD",
  minimumFractionDigits = 2,
): string => {
  if (value == null) return "--";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    minimumFractionDigits,
    maximumFractionDigits: 2,
  }).format(value);
};

export const formatPercent = (value: number | null | undefined, decimals = 2): string => {
  if (value == null) return "--";
  const sign = value >= 0 ? "+" : "";
  return `${sign}${value.toFixed(decimals)}%`;
};

export const formatDate = (
  date: string | Date | null | undefined,
  pattern = "MMM dd, yyyy",
): string => {
  if (date == null) return "--";
  try {
    return format(new Date(date), pattern);
  } catch {
    return "--";
  }
};

export const formatNumber = (value: number | null | undefined): string => {
  if (value == null) return "--";
  if (Math.abs(value) >= 1_000_000_000_000) {
    return `${(value / 1_000_000_000_000).toFixed(2)}T`;
  }
  if (Math.abs(value) >= 1_000_000_000) {
    return `${(value / 1_000_000_000).toFixed(2)}B`;
  }
  if (Math.abs(value) >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(2)}M`;
  }
  if (Math.abs(value) >= 1_000) {
    return `${(value / 1_000).toFixed(2)}K`;
  }
  return value.toFixed(2);
};
