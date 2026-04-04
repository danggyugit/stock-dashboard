import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { formatCurrency, formatDate } from "@/lib/utils";
import type { PerformancePoint } from "@/types";

interface PerformanceChartProps {
  data: PerformancePoint[];
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{
    value: number;
    name: string;
    color: string;
  }>;
  label?: string;
}

const CustomTooltip = ({ active, payload, label }: CustomTooltipProps) => {
  if (!active || !payload || payload.length === 0 || !label) return null;
  return (
    <div className="rounded-md border bg-popover px-3 py-2 text-sm shadow-md">
      <p className="font-medium mb-1">{formatDate(label, "MMM dd, yyyy")}</p>
      {payload.map((entry) => (
        <p key={entry.name} style={{ color: entry.color }}>
          {entry.name}: {formatCurrency(entry.value)}
        </p>
      ))}
    </div>
  );
};

const PerformanceChart = ({ data }: PerformanceChartProps) => {
  if (data.length === 0) return null;

  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
        <XAxis
          dataKey="date"
          tickFormatter={(v: string) => formatDate(v, "MMM dd")}
          tick={{ fontSize: 11 }}
          className="text-muted-foreground"
        />
        <YAxis
          tickFormatter={(v: number) => `$${v.toLocaleString()}`}
          tick={{ fontSize: 11 }}
          className="text-muted-foreground"
          width={80}
        />
        <Tooltip content={<CustomTooltip />} />
        <Legend
          verticalAlign="top"
          iconType="line"
          formatter={(value: string) => (
            <span className="text-xs text-foreground">{value}</span>
          )}
        />
        <Line
          type="monotone"
          dataKey="value"
          name="Portfolio"
          stroke="#3B82F6"
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4 }}
        />
        <Line
          type="monotone"
          dataKey="benchmark_value"
          name="S&P 500"
          stroke="#9CA3AF"
          strokeWidth={1.5}
          strokeDasharray="5 5"
          dot={false}
          activeDot={{ r: 4 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
};

export default PerformanceChart;
