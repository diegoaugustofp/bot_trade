import { useQueryClient } from "@tanstack/react-query";
import {
  useGetBotStatus,
  getGetBotStatusQueryKey,
  useGetBotSummary,
  getGetBotSummaryQueryKey,
  useListTrades,
  getListTradesQueryKey,
  ListTradesStatus,
} from "@workspace/api-client-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  AlertCircle,
  TrendingUp,
  TrendingDown,
  Clock,
  Activity,
  Settings2,
  BarChart2,
  RefreshCcw,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { format } from "date-fns";

const STRATEGY_ABBR: Record<string, string> = {
  ma200_rejection: "MA200",
  ema_crossover:   "EMA",
  pullback_trend:  "Pullback",
  rsi_divergence:  "RSI",
  breakout_nbars:  "Breakout",
  macd_signal:     "MACD",
  poi:             "POI",
};

function strategyAbbr(name?: string | null): string {
  if (!name) return "—";
  return STRATEGY_ABBR[name] ?? name;
}

export default function Dashboard() {
  const queryClient = useQueryClient();
  const { data: status, isLoading: isLoadingStatus } = useGetBotStatus({
    query: {
      refetchInterval: 3000,
      refetchOnWindowFocus: true,
      queryKey: getGetBotStatusQueryKey(),
    }
  });

  const { data: summary, isLoading: isLoadingSummary } = useGetBotSummary({
    query: {
      refetchInterval: 3000,
      refetchOnWindowFocus: true,
      queryKey: getGetBotSummaryQueryKey(),
    }
  });

  const { data: openTrades, isLoading: isLoadingTrades } = useListTrades(
    { status: ListTradesStatus.open },
    {
      query: {
        refetchInterval: 2000,
        refetchOnWindowFocus: true,
        queryKey: getListTradesQueryKey({ status: ListTradesStatus.open }),
      }
    }
  );

  const refreshAll = () => {
    queryClient.invalidateQueries({ queryKey: getGetBotStatusQueryKey() });
    queryClient.invalidateQueries({ queryKey: getGetBotSummaryQueryKey() });
    queryClient.invalidateQueries({ queryKey: getListTradesQueryKey({ status: ListTradesStatus.open }) });
  };

  const formatPrice = (price?: number | null) => price ? price.toFixed(2) : '---';
  const formatPnl = (pnl?: number | null) => {
    if (pnl == null) return '---';
    return (
      <span className={pnl > 0 ? "text-primary" : pnl < 0 ? "text-destructive" : "text-muted-foreground"}>
        {pnl > 0 ? "+" : ""}{pnl.toFixed(2)}
      </span>
    );
  };

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight">OPERATIONS DASHBOARD</h1>
        <div className="flex items-center gap-3">
          <Button variant="outline" size="sm" onClick={refreshAll} className="gap-2">
            <RefreshCcw className="h-4 w-4" />
            Refresh
          </Button>
          {status?.isBlocked && (
            <div className="flex items-center gap-2 rounded-md bg-destructive/20 px-4 py-2 text-destructive font-bold text-sm border border-destructive/50" data-testid="status-blocked">
              <AlertCircle className="h-4 w-4" />
              BLOCKED: {status.blockReason || 'Maximum daily stops reached'}
            </div>
          )}
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card className="bg-card">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">TOTAL PNL</CardTitle>
            <BarChart2 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold" data-testid="summary-total-pnl">
              {isLoadingSummary ? <Skeleton className="h-8 w-24" /> : formatPnl(summary?.totalPnl)}
            </div>
            <div className="text-xs text-muted-foreground mt-1">
              Today: {isLoadingSummary ? <Skeleton className="h-3 w-12 inline-block" /> : formatPnl(summary?.todayPnl)}
            </div>
          </CardContent>
        </Card>
        <Card className="bg-card">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">WIN RATE</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold" data-testid="summary-win-rate">
              {isLoadingSummary ? <Skeleton className="h-8 w-24" /> : `${(summary?.winRate || 0).toFixed(1)}%`}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              W: {summary?.totalWins || 0} / L: {summary?.totalLosses || 0}
            </p>
          </CardContent>
        </Card>
        <Card className="bg-card">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">ACTIVE TRADES</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold" data-testid="summary-open-trades">
              {isLoadingSummary ? <Skeleton className="h-8 w-12" /> : summary?.openTrades || 0}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Total closed: {summary?.closedTrades || 0}
            </p>
          </CardContent>
        </Card>
        <Card className="bg-card">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">DAILY STOPS</CardTitle>
            <Settings2 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold" data-testid="status-daily-stops">
              {isLoadingStatus ? <Skeleton className="h-8 w-12" /> : status?.dailyStops || 0}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Reset at midnight
            </p>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card className="bg-card">
          <CardHeader>
            <CardTitle className="text-sm font-medium">MARKET DATA</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex justify-between items-center border-b border-border pb-2">
              <span className="text-sm text-muted-foreground">Current Price</span>
              <span className="font-mono text-sm" data-testid="status-current-price">
                {isLoadingStatus ? <Skeleton className="h-4 w-16" /> : formatPrice(status?.currentPrice)}
              </span>
            </div>
            <div className="flex justify-between items-center border-b border-border pb-2">
              <span className="text-sm text-muted-foreground">Indicator Level</span>
              <span className="font-mono text-sm" data-testid="status-ma200">
                {isLoadingStatus ? <Skeleton className="h-4 w-16" /> : formatPrice(status?.currentMa200)}
              </span>
            </div>
            <div className="flex justify-between items-center border-b border-border pb-2">
              <span className="text-sm text-muted-foreground">Last Signal</span>
              <span className="font-mono text-sm flex items-center gap-1">
                <Clock className="h-3 w-3 text-muted-foreground" />
                {isLoadingStatus ? <Skeleton className="h-4 w-24" /> : status?.lastSignalAt ? format(new Date(status.lastSignalAt), "HH:mm:ss") : 'None'}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-muted-foreground">Bot Status</span>
              <Badge variant={status?.isRunning ? "default" : "secondary"} className="font-mono" data-testid="status-is-running">
                {isLoadingStatus ? <Skeleton className="h-4 w-16" /> : status?.isRunning ? 'RUNNING' : 'STOPPED'}
              </Badge>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-card">
          <CardHeader>
            <CardTitle className="text-sm font-medium">ACTIVE POSITIONS</CardTitle>
          </CardHeader>
          <CardContent>
            {isLoadingTrades ? (
              <div className="space-y-2">
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
              </div>
            ) : openTrades && openTrades.length > 0 ? (
              <div className="rounded-md border border-border">
                <Table>
                  <TableHeader>
                    <TableRow className="hover:bg-transparent">
                      <TableHead className="text-xs">SYM</TableHead>
                      <TableHead className="text-xs">STRATEGY</TableHead>
                      <TableHead className="text-xs">DIR</TableHead>
                      <TableHead className="text-xs">ENTRY</TableHead>
                      <TableHead className="text-xs">PNL</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {openTrades.map((trade) => (
                      <TableRow key={trade.id} className="hover:bg-accent/50" data-testid={`trade-row-${trade.id}`}>
                        <TableCell className="font-mono text-xs">{trade.symbol}</TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          {strategyAbbr(trade.strategyName)}
                        </TableCell>
                        <TableCell>
                          <span className={`text-xs font-bold ${trade.direction === 'BUY' ? 'text-primary' : 'text-destructive'}`}>
                            {trade.direction}
                          </span>
                        </TableCell>
                        <TableCell className="font-mono text-xs">{trade.entryPrice}</TableCell>
                        <TableCell className="font-mono text-xs text-right">
                          {formatPnl(trade.profitLoss)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-8 text-center">
                <div className="h-8 w-8 rounded-full bg-accent flex items-center justify-center mb-2">
                  <Activity className="h-4 w-4 text-muted-foreground" />
                </div>
                <p className="text-sm text-muted-foreground">No active positions</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
