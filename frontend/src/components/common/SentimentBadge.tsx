import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { SentimentLabel } from "@/types";

interface SentimentBadgeProps {
  label: SentimentLabel | string;
  className?: string;
}

const sentimentColors: Record<string, string> = {
  "Very Bullish": "bg-green-600 text-white hover:bg-green-700",
  Bullish: "bg-green-500 text-white hover:bg-green-600",
  Neutral: "bg-gray-500 text-white hover:bg-gray-600",
  Bearish: "bg-red-500 text-white hover:bg-red-600",
  "Very Bearish": "bg-red-700 text-white hover:bg-red-800",
};

const SentimentBadge = ({ label, className }: SentimentBadgeProps) => {
  const colorClass = sentimentColors[label] ?? sentimentColors["Neutral"];

  return (
    <Badge className={cn(colorClass, className)} variant="default">
      {label}
    </Badge>
  );
};

export default SentimentBadge;
