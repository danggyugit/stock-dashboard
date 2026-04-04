import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { ArrowLeft, FileText, RefreshCw, Sparkles } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { getDailyReport, generateReport } from "@/api/sentiment";
import { formatDate } from "@/lib/utils";
import type { DailyReport } from "@/types";

const AIReport = () => {
  const queryClient = useQueryClient();

  const {
    data: report,
    isLoading,
    error,
  } = useQuery<DailyReport | null>({
    queryKey: ["dailyReport"],
    queryFn: getDailyReport,
    staleTime: 5 * 60_000,
  });

  const generateMutation = useMutation({
    mutationFn: generateReport,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["dailyReport"] });
    },
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <Link to="/sentiment">
            <Button variant="ghost" size="sm" className="mb-2">
              <ArrowLeft className="h-4 w-4 mr-1" />
              Back to Sentiment
            </Button>
          </Link>
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
            <Sparkles className="h-7 w-7" />
            AI Market Report
          </h1>
          <p className="text-muted-foreground">
            AI-generated daily market analysis and summary.
          </p>
        </div>
        <Button
          onClick={() => generateMutation.mutate()}
          disabled={generateMutation.isPending}
        >
          <RefreshCw
            className={`h-4 w-4 mr-1 ${generateMutation.isPending ? "animate-spin" : ""}`}
          />
          {generateMutation.isPending ? "Generating..." : "Generate Report"}
        </Button>
      </div>

      {/* Warning */}
      <Card>
        <CardContent className="py-3">
          <p className="text-xs text-muted-foreground">
            <strong>Note:</strong> Report generation uses the Claude API (billed
            per token). Use the "Generate Report" button sparingly. Reports are
            cached for the day.
          </p>
        </CardContent>
      </Card>

      {/* Report */}
      {isLoading ? (
        <Card>
          <CardHeader>
            <Skeleton className="h-6 w-48" />
          </CardHeader>
          <CardContent className="space-y-3">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-5/6" />
          </CardContent>
        </Card>
      ) : error ? (
        <Card>
          <CardContent className="py-12 text-center">
            <FileText className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <p className="text-muted-foreground">
              Failed to load report. Backend may not be running.
            </p>
            <Button
              variant="outline"
              size="sm"
              className="mt-4"
              onClick={() => generateMutation.mutate()}
            >
              Generate New Report
            </Button>
          </CardContent>
        </Card>
      ) : report && report.content ? (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2">
                <FileText className="h-5 w-5" />
                Daily Report - {formatDate(report.date)}
              </CardTitle>
              <span className="text-xs text-muted-foreground">
                Generated {formatDate(report.generated_at, "MMM dd, yyyy HH:mm")}
              </span>
            </div>
          </CardHeader>
          <Separator />
          <CardContent className="pt-6">
            <div className="prose prose-sm max-w-none dark:prose-invert">
              {report.content.split("\n").map((paragraph, i) => {
                if (!paragraph.trim()) return null;
                if (paragraph.startsWith("###")) {
                  return (
                    <h4 key={i} className="font-semibold mt-6 mb-2">
                      {paragraph.replace(/^#+\s*/, "")}
                    </h4>
                  );
                }
                if (paragraph.startsWith("##")) {
                  return (
                    <h3 key={i} className="font-semibold mt-6 mb-2">
                      {paragraph.replace(/^#+\s*/, "")}
                    </h3>
                  );
                }
                if (paragraph.startsWith("#")) {
                  return (
                    <h2 key={i} className="font-semibold mt-6 mb-2">
                      {paragraph.replace(/^#+\s*/, "")}
                    </h2>
                  );
                }
                if (paragraph.startsWith("- ") || paragraph.startsWith("* ")) {
                  return (
                    <li key={i} className="ml-4 text-sm leading-relaxed">
                      {paragraph.replace(/^[-*]\s*/, "")}
                    </li>
                  );
                }
                return (
                  <p key={i} className="text-sm leading-relaxed mb-3">
                    {paragraph}
                  </p>
                );
              })}
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="py-12 text-center">
            <Sparkles className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <p className="text-lg font-medium mb-2">No report for today</p>
            <p className="text-sm text-muted-foreground mb-4">
              Click "Generate Report" to create today's AI market analysis.
            </p>
            <Button
              onClick={() => generateMutation.mutate()}
              disabled={generateMutation.isPending}
            >
              {generateMutation.isPending
                ? "Generating..."
                : "Generate Report"}
            </Button>
          </CardContent>
        </Card>
      )}

      {generateMutation.isSuccess && (
        <Card>
          <CardContent className="py-3 text-center text-sm text-green-600">
            Report generated successfully! Refreshing...
          </CardContent>
        </Card>
      )}

      {generateMutation.isError && (
        <Card>
          <CardContent className="py-3 text-center text-sm text-destructive">
            Failed to generate report:{" "}
            {(generateMutation.error as Error).message}
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default AIReport;
