import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { formatCurrency } from "@/lib/utils";
import type { AllocationItem } from "@/types";

interface AllocationChartProps {
  data: AllocationItem[];
  title: string;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{
    payload: AllocationItem;
  }>;
}

const CustomTooltip = ({ active, payload }: CustomTooltipProps) => {
  if (!active || !payload || payload.length === 0) return null;
  const item = payload[0].payload;
  return (
    <div className="rounded-md border bg-popover px-3 py-2 text-sm shadow-md">
      <p className="font-medium">{item.label}</p>
      <p className="text-muted-foreground">
        {item.percentage.toFixed(1)}% &middot; {formatCurrency(item.value)}
      </p>
    </div>
  );
};

const AllocationChart = ({ data, title: _title }: AllocationChartProps) => {
  if (data.length === 0) return null;

  return (
    <ResponsiveContainer width="100%" height="100%">
      <PieChart>
        <Pie
          data={data}
          dataKey="value"
          nameKey="label"
          cx="50%"
          cy="50%"
          innerRadius="45%"
          outerRadius="75%"
          paddingAngle={2}
          stroke="none"
        >
          {data.map((item, index) => (
            <Cell key={`cell-${index}`} fill={item.color} />
          ))}
        </Pie>
        <Tooltip content={<CustomTooltip />} />
        <Legend
          verticalAlign="bottom"
          iconType="circle"
          iconSize={8}
          formatter={(value: string) => (
            <span className="text-xs text-foreground">{value}</span>
          )}
        />
      </PieChart>
    </ResponsiveContainer>
  );
};

export default AllocationChart;
