import type { ReactNode } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

interface ChartContainerProps {
  isLoading?: boolean;
  error?: Error | null;
  isEmpty?: boolean;
  emptyMessage?: string;
  height?: string;
  className?: string;
  children: ReactNode;
}

const ChartContainer = ({
  isLoading = false,
  error = null,
  isEmpty = false,
  emptyMessage = "No data available",
  height = "h-80",
  className,
  children,
}: ChartContainerProps) => {
  if (isLoading) {
    return (
      <div className={cn("flex items-center justify-center", height, className)}>
        <Skeleton className="w-full h-full rounded-md" />
      </div>
    );
  }

  if (error) {
    return (
      <div
        className={cn(
          "flex items-center justify-center border border-destructive/20 rounded-md bg-destructive/5",
          height,
          className,
        )}
      >
        <div className="text-center p-4">
          <p className="text-destructive font-medium">Failed to load chart</p>
          <p className="text-sm text-muted-foreground mt-1">
            {error.message || "An unexpected error occurred"}
          </p>
        </div>
      </div>
    );
  }

  if (isEmpty) {
    return (
      <div
        className={cn(
          "flex items-center justify-center border border-dashed rounded-md",
          height,
          className,
        )}
      >
        <p className="text-muted-foreground">{emptyMessage}</p>
      </div>
    );
  }

  return <div className={cn(height, className)}>{children}</div>;
};

export default ChartContainer;
