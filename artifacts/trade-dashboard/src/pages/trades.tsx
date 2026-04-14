import { useState } from "react";
import {
  useListTrades,
  getListTradesQueryKey,
  ListTradesStatus,
} from "@workspace/api-client-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { format } from "date-fns";

type StatusFilter = "all" | "open" | "closed" | "cancelled" | "pending";

const STATUS_COLORS: Record<string, string> = {
  open: "bg-primary/20 text-primary border-primary/30",
  closed: "bg-muted/50 text-muted-foreground border-muted/30",
  cancelled: "bg-destructive/20 text-destructive border-destructive/30",
  pending: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
};

export default function Trades() {
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");

  const { data: trades, isLoading } = useListTrades(
    statusFilter !== "all"
      ? { status: statusFilter as ListTradesStatus, limit: 100 }
      : { limit: 100 },
    {
      query: {
        refetchInterval: 5000,
        queryKey: getListTradesQueryKey(
          statusFilter !== "all"
            ? { status: statusFilter as ListTradesStatus, limit: 100 }
            : { limit: 100 }
        ),
      },
    }
  );

  const filters: { label: string; value: StatusFilter }[] = [
    { label: "All", value: "all" },
    { label: "Open", value: "open" },
    { label: "Pending", value: "pending" },
    { label: "Closed", value: "closed" },
    { label: "Cancelled", value: "cancelled" },
  ];

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight">TRADE HISTORY</h1>
        <span className="text-xs text-muted-foreground font-mono">
          {trades?.length ?? 0} records
        </span>
      </div>

      <div className="flex gap-2" data-testid="filter-tabs">
        {filters.map((f) => (
          <button
            key={f.value}
            data-testid={`filter-${f.value}`}
            onClick={() => setStatusFilter(f.value)}
            className={`px-3 py-1.5 rounded text-xs font-semibold uppercase tracking-wide border transition-colors ${
              statusFilter === f.value
                ? "bg-primary/20 text-primary border-primary/40"
                : "bg-card text-muted-foreground border-border hover:border-primary/30 hover:text-foreground"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="rounded-md border border-border overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="bg-card hover:bg-card border-border">
              <TableHead className="text-muted-foreground text-xs font-semibold uppercase tracking-wide">ID</TableHead>
              <TableHead className="text-muted-foreground text-xs font-semibold uppercase tracking-wide">Symbol</TableHead>
              <TableHead className="text-muted-foreground text-xs font-semibold uppercase tracking-wide">Dir</TableHead>
              <TableHead className="text-muted-foreground text-xs font-semibold uppercase tracking-wide">Status</TableHead>
              <TableHead className="text-muted-foreground text-xs font-semibold uppercase tracking-wide text-right">Order Px</TableHead>
              <TableHead className="text-muted-foreground text-xs font-semibold uppercase tracking-wide text-right">Entry Px</TableHead>
              <TableHead className="text-muted-foreground text-xs font-semibold uppercase tracking-wide text-right">Stop</TableHead>
              <TableHead className="text-muted-foreground text-xs font-semibold uppercase tracking-wide text-right">MA200</TableHead>
              <TableHead className="text-muted-foreground text-xs font-semibold uppercase tracking-wide text-center">P1</TableHead>
              <TableHead className="text-muted-foreground text-xs font-semibold uppercase tracking-wide text-center">P2</TableHead>
              <TableHead className="text-muted-foreground text-xs font-semibold uppercase tracking-wide text-right">PnL</TableHead>
              <TableHead className="text-muted-foreground text-xs font-semibold uppercase tracking-wide">Created</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <TableRow key={i}>
                  {Array.from({ length: 12 }).map((_, j) => (
                    <TableCell key={j}>
                      <Skeleton className="h-4 w-full" />
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : !trades || trades.length === 0 ? (
              <TableRow>
                <TableCell colSpan={12} className="text-center text-muted-foreground py-10">
                  No trades found
                </TableCell>
              </TableRow>
            ) : (
              trades.map((trade) => (
                <TableRow
                  key={trade.id}
                  data-testid={`row-trade-${trade.id}`}
                  className="border-border hover:bg-card/50 transition-colors"
                >
                  <TableCell className="font-mono text-xs text-muted-foreground">
                    #{trade.id}
                  </TableCell>
                  <TableCell className="font-mono text-xs font-semibold">
                    {trade.symbol}
                  </TableCell>
                  <TableCell>
                    <span
                      data-testid={`text-direction-${trade.id}`}
                      className={`text-xs font-bold ${
                        trade.direction === "BUY"
                          ? "text-primary"
                          : "text-destructive"
                      }`}
                    >
                      {trade.direction}
                    </span>
                  </TableCell>
                  <TableCell>
                    <span
                      className={`inline-flex items-center rounded border px-2 py-0.5 text-xs font-semibold uppercase ${
                        STATUS_COLORS[trade.status] ?? ""
                      }`}
                      data-testid={`status-trade-${trade.id}`}
                    >
                      {trade.status}
                    </span>
                  </TableCell>
                  <TableCell className="text-right font-mono text-xs">
                    {trade.orderPrice.toFixed(0)}
                  </TableCell>
                  <TableCell className="text-right font-mono text-xs text-muted-foreground">
                    {trade.entryPrice != null ? trade.entryPrice.toFixed(0) : "---"}
                  </TableCell>
                  <TableCell className="text-right font-mono text-xs text-destructive">
                    {trade.stopLoss.toFixed(0)}
                  </TableCell>
                  <TableCell className="text-right font-mono text-xs text-muted-foreground">
                    {trade.ma200AtEntry.toFixed(0)}
                  </TableCell>
                  <TableCell className="text-center">
                    <span
                      data-testid={`partial1-${trade.id}`}
                      className={`text-xs ${trade.partial1Closed ? "text-primary" : "text-muted-foreground"}`}
                    >
                      {trade.partial1Closed ? "Y" : "N"}
                    </span>
                  </TableCell>
                  <TableCell className="text-center">
                    <span
                      data-testid={`partial2-${trade.id}`}
                      className={`text-xs ${trade.partial2Closed ? "text-primary" : "text-muted-foreground"}`}
                    >
                      {trade.partial2Closed ? "Y" : "N"}
                    </span>
                  </TableCell>
                  <TableCell className="text-right font-mono text-xs">
                    {trade.profitLoss != null ? (
                      <span
                        className={
                          trade.profitLoss > 0
                            ? "text-primary"
                            : trade.profitLoss < 0
                            ? "text-destructive"
                            : "text-muted-foreground"
                        }
                      >
                        {trade.profitLoss > 0 ? "+" : ""}
                        {trade.profitLoss.toFixed(2)}
                      </span>
                    ) : (
                      <span className="text-muted-foreground">---</span>
                    )}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground font-mono">
                    {format(new Date(trade.createdAt), "dd/MM HH:mm")}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
