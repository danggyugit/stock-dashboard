import type { ReactNode } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import PriceChange from "./PriceChange";
import { cn } from "@/lib/utils";

interface MetricCardProps {
  title: string;
  value: string | number;
  change?: number;
  changePct?: number;
  icon?: ReactNode;
  className?: string;
}

const MetricCard = ({ title, value, change, changePct, icon, className }: MetricCardProps) => {
  return (
    <Card className={cn("", className)}>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {title}
        </CardTitle>
        {icon && <div className="text-muted-foreground">{icon}</div>}
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        {(change !== undefined || changePct !== undefined) && (
          <div className="mt-1">
            <PriceChange value={change} percent={changePct} />
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default MetricCard;
