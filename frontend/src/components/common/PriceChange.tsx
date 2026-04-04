import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import { cn, formatCurrency, formatPercent } from "@/lib/utils";

interface PriceChangeProps {
  value?: number;
  percent?: number;
  showIcon?: boolean;
  className?: string;
}

const PriceChange = ({ value, percent, showIcon = true, className }: PriceChangeProps) => {
  const isPositive = (percent ?? value ?? 0) > 0;
  const isNegative = (percent ?? value ?? 0) < 0;
  const isNeutral = !isPositive && !isNegative;

  const colorClass = isPositive
    ? "text-green-600"
    : isNegative
      ? "text-red-600"
      : "text-muted-foreground";

  const Icon = isPositive ? TrendingUp : isNegative ? TrendingDown : Minus;

  return (
    <span className={cn("inline-flex items-center gap-1", colorClass, className)}>
      {showIcon && <Icon className="h-4 w-4" />}
      {value !== undefined && (
        <span>{isNeutral ? "$0.00" : formatCurrency(Math.abs(value))}</span>
      )}
      {percent !== undefined && <span>{formatPercent(percent)}</span>}
    </span>
  );
};

export default PriceChange;
