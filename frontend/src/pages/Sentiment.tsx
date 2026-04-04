import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Brain, ExternalLink, RefreshCw, Search } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
  BarChart, Bar, Line,
} from "recharts";
import ChartContainer from "@/components/common/ChartContainer";
import SentimentBadge from "@/components/common/SentimentBadge";
import FearGreedGauge from "@/components/sentiment/FearGreedGauge";
import {
  getFearGreed,
  getFearGreedHistory,
  getNews,
  getSentimentTrend,
  analyzeSentiment,
} from "@/api/sentiment";
import { formatDate } from "@/lib/utils";
import type {
  FearGreedData,
  FearGreedHistory,
  NewsResponse,
  SentimentTrend,
} from "@/types";

const Sentiment = () => {
  const [historyDays, setHistoryDays] = useState<30 | 90>(30);
  const [tickerQuery, setTickerQuery] = useState("");
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  const [newsPage, setNewsPage] = useState(1);

  const { data: fearGreed, isLoading: fgLoading } = useQuery<FearGreedData>({
    queryKey: ["fearGreed"],
    queryFn: getFearGreed,
    staleTime: 5 * 60_000,
  });

  const {
    data: fgHistory,
    isLoading: fgHistoryLoading,
    error: fgHistoryError,
  } = useQuery<FearGreedHistory>({
    queryKey: ["fearGreedHistory", historyDays],
    queryFn: () => getFearGreedHistory(historyDays),
    staleTime: 5 * 60_000,
  });

  const { data: newsData, isLoading: newsLoading } = useQuery<NewsResponse>({
    queryKey: ["news", selectedTicker, newsPage],
    queryFn: () => getNews(selectedTicker ?? undefined, newsPage),
    staleTime: 2 * 60_000,
  });

  const {
    data: sentimentTrend,
    isLoading: trendLoading,
    error: trendError,
  } = useQuery<SentimentTrend>({
    queryKey: ["sentimentTrend", selectedTicker],
    queryFn: () => getSentimentTrend(selectedTicker!, 30),
    enabled: !!selectedTicker,
    staleTime: 5 * 60_000,
  });

  const analyzeMutation = useMutation({
    mutationFn: () => analyzeSentiment(selectedTicker ?? undefined),
  });

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">
            Market Sentiment
          </h1>
          <p className="text-muted-foreground">
            Fear &amp; Greed index, news sentiment, and AI analysis.
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => analyzeMutation.mutate()}
          disabled={analyzeMutation.isPending}
        >
          <RefreshCw
            className={`h-4 w-4 mr-1 ${analyzeMutation.isPending ? "animate-spin" : ""}`}
          />
          {analyzeMutation.isPending ? "Analyzing..." : "Run Analysis"}
        </Button>
      </div>

      {/* Fear & Greed Section */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Gauge */}
        <Card className="md:col-span-1">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Brain className="h-4 w-4" />
              Fear &amp; Greed Index
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col items-center justify-center">
            {fgLoading ? (
              <div className="space-y-3">
                <Skeleton className="h-24 w-24 rounded-full mx-auto" />
                <Skeleton className="h-6 w-32 mx-auto" />
              </div>
            ) : fearGreed ? (
              <>
                <FearGreedGauge data={fearGreed} />
                <p className="text-xs text-muted-foreground mt-2">
                  Updated {formatDate(fearGreed.updated_at)}
                </p>
              </>
            ) : (
              <p className="text-muted-foreground text-sm">
                Fear &amp; Greed data unavailable
              </p>
            )}
          </CardContent>
        </Card>

        {/* F&G History Chart */}
        <Card className="md:col-span-2">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">
                Fear &amp; Greed History
              </CardTitle>
              <Tabs
                value={historyDays.toString()}
                onValueChange={(v) => setHistoryDays(Number(v) as 30 | 90)}
              >
                <TabsList className="h-8">
                  <TabsTrigger value="30" className="text-xs px-3">
                    30D
                  </TabsTrigger>
                  <TabsTrigger value="90" className="text-xs px-3">
                    90D
                  </TabsTrigger>
                </TabsList>
              </Tabs>
            </div>
          </CardHeader>
          <CardContent>
            <ChartContainer
              isLoading={fgHistoryLoading}
              error={fgHistoryError as Error | null}
              isEmpty={!fgHistory || fgHistory.length === 0}
              height="h-64"
            >
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={fgHistory ?? []}>
                  <defs>
                    <linearGradient id="fgGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#eab308" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#eab308" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 10 }}
                    tickFormatter={(v: string) => v.slice(5)}
                    minTickGap={30}
                  />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 10 }} />
                  <Tooltip
                    labelFormatter={(v) => String(v)}
                    formatter={(v) => [`${Number(v).toFixed(1)}`, "Score"]}
                  />
                  <Area
                    type="monotone"
                    dataKey="score"
                    stroke="#eab308"
                    fill="url(#fgGrad)"
                    strokeWidth={2}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </ChartContainer>
          </CardContent>
        </Card>
      </div>

      <Separator />

      {/* Ticker Sentiment Search */}
      <div>
        <h2 className="text-xl font-semibold mb-4">Stock Sentiment</h2>
        <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center mb-4">
          <div className="relative w-full sm:w-72">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Enter ticker (e.g. AAPL)..."
              className="pl-9"
              value={tickerQuery}
              onChange={(e) => setTickerQuery(e.target.value.toUpperCase())}
              onKeyDown={(e) => {
                if (e.key === "Enter" && tickerQuery.trim()) {
                  setSelectedTicker(tickerQuery.trim());
                  setNewsPage(1);
                }
              }}
            />
          </div>
          <Button
            size="sm"
            onClick={() => {
              if (tickerQuery.trim()) {
                setSelectedTicker(tickerQuery.trim());
                setNewsPage(1);
              }
            }}
          >
            Search
          </Button>
          {selectedTicker && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setSelectedTicker(null);
                setTickerQuery("");
              }}
            >
              Clear
            </Button>
          )}
        </div>

        {/* Sentiment Trend */}
        {selectedTicker && (
          <Card className="mb-6">
            <CardHeader>
              <CardTitle className="text-base">
                {selectedTicker} Sentiment Trend (30D)
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ChartContainer
                isLoading={trendLoading}
                error={trendError as Error | null}
                isEmpty={
                  !sentimentTrend || sentimentTrend.trend.length === 0
                }
                height="h-48"
              >
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={sentimentTrend?.trend ?? []}>
                    <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={(v: string) => v.slice(5)} />
                    <YAxis yAxisId="left" tick={{ fontSize: 10 }} />
                    <YAxis yAxisId="right" orientation="right" domain={[-1, 1]} tick={{ fontSize: 10 }} />
                    <Tooltip />
                    <Bar yAxisId="left" dataKey="article_count" fill="#6366f1" opacity={0.6} name="Articles" />
                    <Line yAxisId="right" type="monotone" dataKey="avg_sentiment" stroke="#22c55e" strokeWidth={2} name="Sentiment" dot={false} />
                  </BarChart>
                </ResponsiveContainer>
              </ChartContainer>
            </CardContent>
          </Card>
        )}
      </div>

      {/* News Feed */}
      <div>
        <h2 className="text-xl font-semibold mb-4">
          {selectedTicker ? `${selectedTicker} News` : "Market News"}
        </h2>
        {newsLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-20 w-full" />
            ))}
          </div>
        ) : newsData && newsData.articles.length > 0 ? (
          <div className="space-y-3">
            {newsData.articles.map((article) => (
              <Card key={article.id}>
                <CardContent className="py-3">
                  <div className="flex items-start gap-3">
                    <div className="flex-1 min-w-0">
                      <a
                        href={article.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-medium text-sm hover:underline flex items-center gap-1"
                      >
                        {article.headline}
                        <ExternalLink className="h-3 w-3 flex-shrink-0" />
                      </a>
                      <div className="flex items-center gap-2 mt-1 flex-wrap">
                        <span className="text-xs text-muted-foreground">
                          {article.source}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {formatDate(article.published_at)}
                        </span>
                        {article.ticker && (
                          <span className="text-xs font-medium">
                            {article.ticker}
                          </span>
                        )}
                        {article.sentiment_label && (
                          <SentimentBadge label={article.sentiment_label} />
                        )}
                      </div>
                      {article.ai_summary && (
                        <p className="text-xs text-muted-foreground mt-2">
                          {article.ai_summary}
                        </p>
                      )}
                    </div>
                    {article.sentiment !== undefined && (
                      <div className="text-right flex-shrink-0">
                        <span
                          className={`text-sm font-bold ${
                            article.sentiment > 0
                              ? "text-green-600"
                              : article.sentiment < 0
                                ? "text-red-600"
                                : "text-gray-500"
                          }`}
                        >
                          {article.sentiment > 0 ? "+" : ""}
                          {article.sentiment.toFixed(2)}
                        </span>
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            ))}
            {/* Pagination */}
            <div className="flex justify-center gap-2 pt-4">
              <Button
                variant="outline"
                size="sm"
                disabled={newsPage <= 1}
                onClick={() => setNewsPage((p) => p - 1)}
              >
                Previous
              </Button>
              <span className="text-sm text-muted-foreground flex items-center">
                Page {newsPage}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={
                  newsData.articles.length < (newsData.page_size ?? 20)
                }
                onClick={() => setNewsPage((p) => p + 1)}
              >
                Next
              </Button>
            </div>
          </div>
        ) : (
          <Card>
            <CardContent className="py-8 text-center text-muted-foreground">
              No news articles available
              {selectedTicker ? ` for ${selectedTicker}` : ""}.
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
};

export default Sentiment;
