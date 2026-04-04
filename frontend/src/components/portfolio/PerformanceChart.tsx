import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import { formatDate } from "@/lib/utils";
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
          {entry.name}: {entry.value != null ? `${entry.value >= 0 ? "+" : ""}${entry.value.toFixed(2)}%` : "--"}
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
          tickFormatter={(v: number) => `${v >= 0 ? "+" : ""}${v}%`}
          tick={{ fontSize: 11 }}
          className="text-muted-foreground"
          width={60}
        />
        <ReferenceLine y={0} stroke="#9CA3AF" strokeDasharray="3 3" />
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
          dataKey="gain_pct"
          name="Portfolio"
          stroke="#3B82F6"
          strokeWidth={2.5}
          dot={false}
          activeDot={{ r: 4 }}
        />
        <Line
          type="monotone"
          dataKey="spy_pct"
          name="SPY"
          stroke="#10B981"
          strokeWidth={1.5}
          dot={false}
          activeDot={{ r: 3 }}
          connectNulls
        />
        <Line
          type="monotone"
          dataKey="qqq_pct"
          name="QQQ"
          stroke="#F97316"
          strokeWidth={1.5}
          dot={false}
          activeDot={{ r: 3 }}
          connectNulls
        />
      </LineChart>
    </ResponsiveContainer>
  );
};

export default PerformanceChart;
