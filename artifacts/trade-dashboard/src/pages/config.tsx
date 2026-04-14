import React, { useState, useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  useListSymbolConfigs,
  getListSymbolConfigsQueryKey,
  useCreateSymbolConfig,
  useUpdateSymbolConfigById,
  useDeleteSymbolConfigById,
  useGetBotSettings,
  useUpdateBotSettings,
} from "@workspace/api-client-react";
import type { BotConfig, BotConfigInput } from "@workspace/api-client-react";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { useToast } from "@/hooks/use-toast";
import { useQueryClient } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Plus, Pencil, Trash2, Save, X, MessageSquare, CheckCircle2, XCircle } from "lucide-react";

const STRATEGY_OPTIONS = [
  { value: "ma200_rejection", label: "MA200 Rejection" },
  { value: "ema_crossover", label: "EMA Crossover" },
  { value: "pullback_trend", label: "Pullback Trend" },
  { value: "rsi_divergence", label: "RSI Divergence" },
  { value: "breakout_nbars", label: "Breakout N-Bars" },
  { value: "macd_signal", label: "MACD Signal" },
  { value: "poi", label: "POI (Point of Interest)" },
];

type ParamField =
  | { key: string; label: string; type: "number" }
  | { key: string; label: string; type: "array"; placeholder?: string }
  | { key: string; label: string; type: "select"; options: { value: string; label: string }[] };

const STRATEGY_PARAM_FIELDS: Record<string, ParamField[]> = {
  ma200_rejection: [
    { key: "ma_period", label: "MA Period", type: "number" },
    {
      key: "ma_type",
      label: "MA Type",
      type: "select",
      options: [
        { value: "SMA", label: "SMA" },
        { value: "EMA", label: "EMA" },
      ],
    },
    { key: "touch_threshold", label: "Touch Threshold (ticks)", type: "number" },
    { key: "rejection_candles", label: "Rejection Candles", type: "number" },
    { key: "min_distance_pts", label: "Min Distance (ticks)", type: "number" },
  ],
  ema_crossover: [
    { key: "fast_period", label: "Fast EMA Period", type: "number" },
    { key: "slow_period", label: "Slow EMA Period", type: "number" },
    { key: "confirmation_candles", label: "Confirmation Candles", type: "number" },
  ],
  pullback_trend: [
    { key: "trend_ema_period", label: "Trend EMA Period", type: "number" },
    { key: "touch_threshold", label: "Touch Threshold (ticks)", type: "number" },
    { key: "confirmation_candles", label: "Confirmation Candles", type: "number" },
    { key: "trend_lookback", label: "Trend Lookback (bars)", type: "number" },
  ],
  rsi_divergence: [
    { key: "rsi_period", label: "RSI Period", type: "number" },
    { key: "lookback_bars", label: "Lookback Bars", type: "number" },
    { key: "rsi_overbought", label: "RSI Overbought", type: "number" },
    { key: "rsi_oversold", label: "RSI Oversold", type: "number" },
  ],
  breakout_nbars: [
    { key: "lookback_bars", label: "Lookback Bars", type: "number" },
    { key: "min_range", label: "Min Range (ticks)", type: "number" },
  ],
  macd_signal: [
    { key: "fast_period", label: "Fast Period", type: "number" },
    { key: "slow_period", label: "Slow Period", type: "number" },
    { key: "signal_period", label: "Signal Period", type: "number" },
  ],
  poi: [
    {
      key: "buy_levels",
      label: "Buy Levels (price)",
      type: "array",
      placeholder: "ex: 125000, 124500",
    },
    {
      key: "sell_levels",
      label: "Sell Levels (price)",
      type: "array",
      placeholder: "ex: 126000, 126500",
    },
    { key: "touch_threshold", label: "Touch Threshold (ticks)", type: "number" },
    { key: "rejection_candles", label: "Rejection Candles", type: "number" },
  ],
};

const hhmmRegex = /^([01]\d|2[0-3]):[0-5]\d$/;

const configSchema = z.object({
  symbol: z.string().min(1, "Required"),
  strategyName: z.string().min(1, "Required"),
  lotSize: z.coerce.number().positive("Must be positive"),
  timeframeMinutes: z.coerce.number().int().positive("Must be positive"),
  ma200Period: z.coerce.number().int().positive("Must be positive"),
  entryOffset: z.coerce.number().positive("Must be positive"),
  stopLoss: z.coerce.number().positive("Must be positive"),
  partial1Percent: z.coerce.number().min(1).max(100),
  partial1Points: z.coerce.number().positive(),
  partial2Percent: z.coerce.number().min(1).max(100),
  partial2Points: z.coerce.number().positive(),
  partial3Points: z.coerce.number().positive(),
  tradingStartTime: z
    .string()
    .optional()
    .refine((v) => !v || hhmmRegex.test(v), { message: "Format: HH:MM" }),
  tradingEndTime: z
    .string()
    .optional()
    .refine((v) => !v || hhmmRegex.test(v), { message: "Format: HH:MM" }),
  forceCloseTime: z
    .string()
    .optional()
    .refine((v) => !v || hhmmRegex.test(v), { message: "Format: HH:MM" }),
  maxOpenTrades: z.coerce.number().int().min(1).max(10),
  maxDailyStops: z.coerce.number().int().min(1).max(20),
  maxDailyLossPts: z.union([z.coerce.number().positive(), z.literal("")]).optional(),
  maxDailyProfitPts: z.union([z.coerce.number().positive(), z.literal("")]).optional(),
  breakEvenPts: z.union([z.coerce.number().positive(), z.literal("")]).optional(),
  cancelPendingAfterBars: z.union([z.coerce.number().int().positive(), z.literal("")]).optional(),
});

type ConfigForm = z.infer<typeof configSchema>;

const DEFAULT_VALUES: ConfigForm = {
  symbol: "",
  strategyName: "ma200_rejection",
  lotSize: 1,
  timeframeMinutes: 5,
  ma200Period: 200,
  entryOffset: 10,
  stopLoss: 20,
  partial1Percent: 60,
  partial1Points: 20,
  partial2Percent: 20,
  partial2Points: 50,
  partial3Points: 100,
  tradingStartTime: "",
  tradingEndTime: "",
  forceCloseTime: "",
  maxOpenTrades: 3,
  maxDailyStops: 2,
  maxDailyLossPts: "",
  maxDailyProfitPts: "",
  breakEvenPts: "",
  cancelPendingAfterBars: "",
};

function nullToStr(v: string | null | undefined) {
  return v ?? "";
}

function configToForm(cfg: BotConfig): ConfigForm {
  return {
    symbol: cfg.symbol,
    strategyName: cfg.strategyName,
    lotSize: cfg.lotSize,
    timeframeMinutes: cfg.timeframeMinutes,
    ma200Period: cfg.ma200Period,
    entryOffset: cfg.entryOffset,
    stopLoss: cfg.stopLoss,
    partial1Percent: cfg.partial1Percent,
    partial1Points: cfg.partial1Points,
    partial2Percent: cfg.partial2Percent,
    partial2Points: cfg.partial2Points,
    partial3Points: cfg.partial3Points,
    tradingStartTime: nullToStr(cfg.tradingStartTime),
    tradingEndTime: nullToStr(cfg.tradingEndTime),
    forceCloseTime: nullToStr(cfg.forceCloseTime),
    maxOpenTrades: cfg.maxOpenTrades,
    maxDailyStops: cfg.maxDailyStops,
    maxDailyLossPts: cfg.maxDailyLossPts ?? "",
    maxDailyProfitPts: cfg.maxDailyProfitPts ?? "",
    breakEvenPts: cfg.breakEvenPts ?? "",
    cancelPendingAfterBars: cfg.cancelPendingAfterBars ?? "",
  };
}

function formToPayload(
  data: ConfigForm,
  strategyParams: Record<string, unknown>
): BotConfigInput {
  function toNullableNum(v: unknown): number | null {
    if (v === "" || v === null || v === undefined) return null;
    const n = Number(v);
    return isNaN(n) ? null : n;
  }
  return {
    symbol: data.symbol,
    strategyName: data.strategyName,
    strategyParams,
    lotSize: data.lotSize,
    timeframeMinutes: data.timeframeMinutes,
    ma200Period: data.ma200Period,
    entryOffset: data.entryOffset,
    stopLoss: data.stopLoss,
    partial1Percent: data.partial1Percent,
    partial1Points: data.partial1Points,
    partial2Percent: data.partial2Percent,
    partial2Points: data.partial2Points,
    partial3Points: data.partial3Points,
    tradingStartTime: data.tradingStartTime || null,
    tradingEndTime: data.tradingEndTime || null,
    forceCloseTime: data.forceCloseTime || null,
    maxOpenTrades: data.maxOpenTrades,
    maxDailyStops: data.maxDailyStops,
    maxDailyLossPts: toNullableNum(data.maxDailyLossPts),
    maxDailyProfitPts: toNullableNum(data.maxDailyProfitPts),
    breakEvenPts: toNullableNum(data.breakEvenPts),
    cancelPendingAfterBars: toNullableNum(data.cancelPendingAfterBars),
  };
}

function FieldRow({
  label,
  desc,
  children,
}: {
  label: string;
  desc?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="grid grid-cols-3 gap-4 items-start py-3 border-b border-border last:border-0">
      <div>
        <div className="text-sm font-semibold text-foreground">{label}</div>
        {desc && <div className="text-xs text-muted-foreground mt-0.5">{desc}</div>}
      </div>
      <div className="col-span-2">{children}</div>
    </div>
  );
}

function StrategyParamFields({
  strategyName,
  strategyParams,
  onChange,
}: {
  strategyName: string;
  strategyParams: Record<string, unknown>;
  onChange: (key: string, value: unknown) => void;
}) {
  const fields = STRATEGY_PARAM_FIELDS[strategyName] ?? [];
  if (fields.length === 0) return null;

  return (
    <>
      {fields.map((field) => (
        <FieldRow key={field.key} label={field.label}>
          {field.type === "select" ? (
            <Select
              value={String(strategyParams[field.key] ?? field.options[0].value)}
              onValueChange={(v) => onChange(field.key, v)}
            >
              <SelectTrigger className="font-mono">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {field.options.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          ) : field.type === "array" ? (
            <Input
              type="text"
              className="font-mono"
              placeholder={field.placeholder}
              value={
                Array.isArray(strategyParams[field.key])
                  ? (strategyParams[field.key] as number[]).join(", ")
                  : String(strategyParams[field.key] ?? "")
              }
              onChange={(e) => {
                const nums = e.target.value
                  .split(",")
                  .map((s) => s.trim())
                  .filter((s) => s !== "")
                  .map(Number)
                  .filter((n) => !isNaN(n));
                onChange(field.key, nums);
              }}
            />
          ) : (
            <Input
              type="number"
              className="font-mono"
              value={String(strategyParams[field.key] ?? "")}
              onChange={(e) =>
                onChange(
                  field.key,
                  e.target.value === "" ? "" : Number(e.target.value)
                )
              }
            />
          )}
        </FieldRow>
      ))}
    </>
  );
}

function StrategyRow({
  config,
  onEdit,
  onDelete,
}: {
  config: BotConfig;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const strategyLabel =
    STRATEGY_OPTIONS.find((s) => s.value === config.strategyName)?.label ??
    config.strategyName;

  return (
    <div
      className="flex items-center justify-between py-2 px-3 rounded-md hover:bg-accent/30 transition-colors group"
      data-testid={`strategy-row-${config.id ?? config.strategyName}`}
    >
      <div className="flex items-center gap-3 min-w-0">
        <Badge
          variant="outline"
          className="font-mono text-xs shrink-0 border-primary/40 text-primary"
        >
          {strategyLabel}
        </Badge>
        <span className="text-xs text-muted-foreground">
          Lot: {config.lotSize} · TF: M{config.timeframeMinutes}
        </span>
      </div>
      <div className="flex gap-1 shrink-0">
        <Button
          size="sm"
          variant="ghost"
          data-testid={`btn-edit-${config.id ?? config.symbol}`}
          onClick={onEdit}
          className="h-7 px-2 text-xs opacity-70 group-hover:opacity-100"
        >
          <Pencil className="h-3 w-3 mr-1" />
          Edit
        </Button>
        <Button
          size="sm"
          variant="ghost"
          data-testid={`btn-delete-${config.id ?? config.symbol}`}
          onClick={onDelete}
          className="h-7 px-2 text-xs text-destructive hover:text-destructive opacity-70 group-hover:opacity-100"
        >
          <Trash2 className="h-3 w-3 mr-1" />
          Remove
        </Button>
      </div>
    </div>
  );
}

function SymbolGroup({
  symbol,
  configs,
  onEdit,
  onDelete,
}: {
  symbol: string;
  configs: BotConfig[];
  onEdit: (cfg: BotConfig) => void;
  onDelete: (cfg: BotConfig) => void;
}) {
  return (
    <Card className="border-border bg-card">
      <CardContent className="pt-4 pb-3">
        <div className="flex items-center gap-2 pb-3 border-b border-border mb-1">
          <span className="text-base font-bold font-mono tracking-tight text-foreground">
            {symbol}
          </span>
          <span className="text-xs text-muted-foreground">
            {configs.length === 1 ? "1 strategy" : `${configs.length} strategies`}
          </span>
        </div>
        <div className="space-y-0.5 pt-1">
          {configs.map((cfg) => (
            <StrategyRow
              key={cfg.id ?? cfg.strategyName}
              config={cfg}
              onEdit={() => onEdit(cfg)}
              onDelete={() => onDelete(cfg)}
            />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

export default function Config() {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const [sheetOpen, setSheetOpen] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editingSymbol, setEditingSymbol] = useState<string | null>(null);
  const [strategyParams, setStrategyParams] = useState<Record<string, unknown>>({});
  const [deleteTarget, setDeleteTarget] = useState<number | null>(null);

  const { data: configs, isLoading } = useListSymbolConfigs();

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: getListSymbolConfigsQueryKey() });
  };

  const createConfig = useCreateSymbolConfig({
    mutation: {
      onSuccess: () => {
        invalidate();
        setSheetOpen(false);
        toast({ title: "Symbol created", description: "Configuration saved successfully." });
      },
      onError: (err: unknown) => {
        const msg =
          (err as { response?: { data?: { error?: string } } })?.response?.data?.error ??
          String(err);
        toast({ title: "Error creating symbol", description: msg, variant: "destructive" });
      },
    },
  });

  const updateConfig = useUpdateSymbolConfigById({
    mutation: {
      onSuccess: () => {
        invalidate();
        setSheetOpen(false);
        toast({ title: "Configuration saved", description: "Symbol config updated successfully." });
      },
      onError: (err: unknown) => {
        const msg =
          (err as { response?: { data?: { error?: string } } })?.response?.data?.error ??
          String(err);
        toast({ title: "Error saving configuration", description: msg, variant: "destructive" });
      },
    },
  });

  const deleteConfig = useDeleteSymbolConfigById({
    mutation: {
      onSuccess: () => {
        invalidate();
        toast({ title: "Symbol removed", description: "Configuration deleted." });
      },
      onError: (err: unknown) => {
        toast({
          title: "Error removing symbol",
          description: String(err),
          variant: "destructive",
        });
      },
    },
  });

  const form = useForm<ConfigForm>({
    resolver: zodResolver(configSchema),
    defaultValues: DEFAULT_VALUES,
  });

  const watchedStrategyName = form.watch("strategyName");

  useEffect(() => {
    if (!sheetOpen) {
      setStrategyParams({});
      setIsCreating(false);
      setEditingId(null);
      setEditingSymbol(null);
    }
  }, [sheetOpen]);


  function openCreate() {
    form.reset(DEFAULT_VALUES);
    setStrategyParams({});
    setIsCreating(true);
    setEditingSymbol(null);
    setSheetOpen(true);
  }

  function openEdit(config: BotConfig) {
    form.reset(configToForm(config));
    setStrategyParams(
      typeof config.strategyParams === "object" && config.strategyParams !== null
        ? (config.strategyParams as Record<string, unknown>)
        : {}
    );
    setIsCreating(false);
    setEditingId(config.id ?? null);
    setEditingSymbol(config.symbol);
    setSheetOpen(true);
  }

  function onSubmit(data: ConfigForm) {
    const payload = formToPayload(data, strategyParams);
    if (isCreating) {
      createConfig.mutate({ data: payload });
    } else if (editingId != null) {
      updateConfig.mutate({ id: editingId, data: payload });
    }
  }

  function onParamChange(key: string, value: unknown) {
    setStrategyParams((prev) => ({ ...prev, [key]: value }));
  }

  const isMutating = createConfig.isPending || updateConfig.isPending;

  const { data: botSettings } = useGetBotSettings();
  const updateSettings = useUpdateBotSettings({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["bot-settings"] });
      },
    },
  });

  function toggleDiscord(enabled: boolean) {
    updateSettings.mutate({ data: { discordEnabled: enabled } });
  }

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight">CONFIGURATION</h1>
        <Button
          size="sm"
          data-testid="btn-add-symbol"
          onClick={openCreate}
          className="flex items-center gap-2"
        >
          <Plus className="h-4 w-4" />
          Add Symbol / Strategy
        </Button>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
      ) : !configs || configs.length === 0 ? (
        <Card className="border-border bg-card">
          <CardContent className="flex flex-col items-center justify-center py-12 text-center">
            <p className="text-muted-foreground mb-4">No symbols configured yet.</p>
            <Button onClick={openCreate} variant="outline" size="sm">
              <Plus className="h-4 w-4 mr-2" />
              Add your first symbol
            </Button>
          </CardContent>
        </Card>
      ) : (() => {
        const groups = configs.reduce<Record<string, BotConfig[]>>((acc, cfg) => {
          if (!acc[cfg.symbol]) acc[cfg.symbol] = [];
          acc[cfg.symbol].push(cfg);
          return acc;
        }, {});
        const sortedSymbols = Object.keys(groups).sort();
        return (
          <div className="space-y-4">
            {sortedSymbols.map((sym) => (
              <SymbolGroup
                key={sym}
                symbol={sym}
                configs={groups[sym]}
                onEdit={openEdit}
                onDelete={(cfg) => setDeleteTarget(cfg.id ?? null)}
              />
            ))}
          </div>
        );
      })()}

      <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
        <SheetContent
          side="right"
          className="w-full sm:max-w-xl overflow-y-auto"
          data-testid="symbol-config-sheet"
        >
          <SheetHeader className="mb-4">
            <SheetTitle>
              {isCreating
                ? "Add Symbol / Strategy"
                : `Edit: ${editingSymbol} — ${
                    STRATEGY_OPTIONS.find((s) => s.value === watchedStrategyName)?.label ??
                    watchedStrategyName
                  }`}
            </SheetTitle>
            <SheetDescription>
              {isCreating
                ? "Configure a new symbol and strategy pair."
                : "Update the configuration for this symbol/strategy."}
            </SheetDescription>
          </SheetHeader>

          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
              <Card className="border-border bg-card">
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">General</CardTitle>
                  <CardDescription>Symbol and position settings</CardDescription>
                </CardHeader>
                <CardContent>
                  <FormField
                    control={form.control}
                    name="symbol"
                    render={({ field }) => (
                      <FieldRow label="Symbol" desc="Trading instrument">
                        <FormItem>
                          <FormControl>
                            <Input
                              {...field}
                              data-testid="input-symbol"
                              className="font-mono"
                              readOnly={!isCreating}
                              disabled={!isCreating}
                            />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      </FieldRow>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="strategyName"
                    render={({ field }) => (
                      <FieldRow label="Strategy" desc="Active strategy module">
                        <FormItem>
                          <Select
                            value={field.value}
                            onValueChange={(v) => { field.onChange(v); setStrategyParams({}); }}
                          >
                            <FormControl>
                              <SelectTrigger
                                data-testid="select-strategy"
                                className="font-mono"
                              >
                                <SelectValue />
                              </SelectTrigger>
                            </FormControl>
                            <SelectContent>
                              {STRATEGY_OPTIONS.map((s) => (
                                <SelectItem key={s.value} value={s.value}>
                                  {s.label}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                          <FormMessage />
                        </FormItem>
                      </FieldRow>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="lotSize"
                    render={({ field }) => (
                      <FieldRow label="Position Size" desc="Lots / contracts per trade">
                        <FormItem>
                          <FormControl>
                            <Input
                              {...field}
                              type="number"
                              step="0.1"
                              data-testid="input-lot-size"
                              className="font-mono"
                            />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      </FieldRow>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="timeframeMinutes"
                    render={({ field }) => (
                      <FieldRow label="Timeframe (min)" desc="Candle period (5 = M5)">
                        <FormItem>
                          <FormControl>
                            <Input
                              {...field}
                              type="number"
                              data-testid="input-timeframe"
                              className="font-mono"
                            />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      </FieldRow>
                    )}
                  />
                </CardContent>
              </Card>

              <Card className="border-border bg-card">
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">Strategy Parameters</CardTitle>
                  <CardDescription>
                    Dynamic parameters for{" "}
                    {STRATEGY_OPTIONS.find((s) => s.value === watchedStrategyName)?.label ??
                      watchedStrategyName}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <StrategyParamFields
                    strategyName={watchedStrategyName}
                    strategyParams={strategyParams}
                    onChange={onParamChange}
                  />
                </CardContent>
              </Card>

              <Card className="border-border bg-card">
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">Entry & Stop</CardTitle>
                  <CardDescription>
                    Order placement parameters and partial exit levels
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {watchedStrategyName === "ma200_rejection" && (
                    <FormField
                      control={form.control}
                      name="ma200Period"
                      render={({ field }) => (
                        <FieldRow label="MA Period" desc="Moving average lookback period">
                          <FormItem>
                            <FormControl>
                              <Input
                                {...field}
                                type="number"
                                data-testid="input-ma-period"
                                className="font-mono"
                              />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        </FieldRow>
                      )}
                    />
                  )}
                  <FormField
                    control={form.control}
                    name="entryOffset"
                    render={({ field }) => (
                      <FieldRow
                        label="Entry Offset (ticks)"
                        desc="Limit order offset from signal level"
                      >
                        <FormItem>
                          <FormControl>
                            <Input
                              {...field}
                              type="number"
                              step="1"
                              data-testid="input-entry-offset"
                              className="font-mono"
                            />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      </FieldRow>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="stopLoss"
                    render={({ field }) => (
                      <FieldRow label="Stop Loss (ticks)" desc="Stop loss distance from entry">
                        <FormItem>
                          <FormControl>
                            <Input
                              {...field}
                              type="number"
                              step="1"
                              data-testid="input-stop-loss"
                              className="font-mono"
                            />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      </FieldRow>
                    )}
                  />

                  <div className="grid grid-cols-2 gap-4 py-3 border-b border-border">
                    <div className="col-span-2 text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1">
                      1st Partial
                    </div>
                    <FormField
                      control={form.control}
                      name="partial1Percent"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel className="text-xs">% of Position</FormLabel>
                          <FormControl>
                            <Input
                              {...field}
                              type="number"
                              step="1"
                              data-testid="input-p1-pct"
                              className="font-mono"
                            />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <FormField
                      control={form.control}
                      name="partial1Points"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel className="text-xs">Target (ticks)</FormLabel>
                          <FormControl>
                            <Input
                              {...field}
                              type="number"
                              step="1"
                              data-testid="input-p1-pts"
                              className="font-mono"
                            />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-4 py-3 border-b border-border">
                    <div className="col-span-2 text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1">
                      2nd Partial
                    </div>
                    <FormField
                      control={form.control}
                      name="partial2Percent"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel className="text-xs">% of Position</FormLabel>
                          <FormControl>
                            <Input
                              {...field}
                              type="number"
                              step="1"
                              data-testid="input-p2-pct"
                              className="font-mono"
                            />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <FormField
                      control={form.control}
                      name="partial2Points"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel className="text-xs">Target (ticks)</FormLabel>
                          <FormControl>
                            <Input
                              {...field}
                              type="number"
                              step="1"
                              data-testid="input-p2-pts"
                              className="font-mono"
                            />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  </div>

                  <div className="py-3">
                    <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">
                      3rd Partial (remainder)
                    </div>
                    <FormField
                      control={form.control}
                      name="partial3Points"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel className="text-xs">Target (ticks)</FormLabel>
                          <FormControl>
                            <Input
                              {...field}
                              type="number"
                              step="1"
                              data-testid="input-p3-pts"
                              className="font-mono w-1/2"
                            />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  </div>
                </CardContent>
              </Card>

              <Card className="border-border bg-card">
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">Trading Schedule</CardTitle>
                  <CardDescription>
                    Leave blank for no time restriction
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <FormField
                    control={form.control}
                    name="tradingStartTime"
                    render={({ field }) => (
                      <FieldRow label="Start Time" desc="Earliest entry time (HH:MM)">
                        <FormItem>
                          <FormControl>
                            <Input
                              {...field}
                              placeholder="e.g. 09:00"
                              data-testid="input-trading-start"
                              className="font-mono"
                            />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      </FieldRow>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="tradingEndTime"
                    render={({ field }) => (
                      <FieldRow label="End Time" desc="Latest entry time (HH:MM)">
                        <FormItem>
                          <FormControl>
                            <Input
                              {...field}
                              placeholder="e.g. 17:00"
                              data-testid="input-trading-end"
                              className="font-mono"
                            />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      </FieldRow>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="forceCloseTime"
                    render={({ field }) => (
                      <FieldRow label="Force Close" desc="Close all positions at (HH:MM)">
                        <FormItem>
                          <FormControl>
                            <Input
                              {...field}
                              placeholder="e.g. 17:30"
                              data-testid="input-force-close"
                              className="font-mono"
                            />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      </FieldRow>
                    )}
                  />
                </CardContent>
              </Card>

              <Card className="border-border bg-card">
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">Risk Management</CardTitle>
                  <CardDescription>
                    Position limits and daily stop rules
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <FormField
                    control={form.control}
                    name="maxOpenTrades"
                    render={({ field }) => (
                      <FieldRow label="Max Open Trades" desc="Simultaneous position limit">
                        <FormItem>
                          <FormControl>
                            <Input
                              {...field}
                              type="number"
                              data-testid="input-max-trades"
                              className="font-mono"
                            />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      </FieldRow>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="maxDailyStops"
                    render={({ field }) => (
                      <FieldRow label="Max Daily Stops" desc="Block after this many stops/day">
                        <FormItem>
                          <FormControl>
                            <Input
                              {...field}
                              type="number"
                              data-testid="input-max-stops"
                              className="font-mono"
                            />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      </FieldRow>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="maxDailyLossPts"
                    render={({ field }) => (
                      <FieldRow
                        label="Max Daily Loss (ticks)"
                        desc="Optional — stop opening trades after this daily loss"
                      >
                        <FormItem>
                          <FormControl>
                            <Input
                              {...field}
                              type="number"
                              step="1"
                              placeholder="—"
                              data-testid="input-max-daily-loss"
                              className="font-mono"
                              value={field.value as string | number}
                            />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      </FieldRow>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="maxDailyProfitPts"
                    render={({ field }) => (
                      <FieldRow
                        label="Max Daily Profit (ticks)"
                        desc="Optional — stop after reaching this daily profit"
                      >
                        <FormItem>
                          <FormControl>
                            <Input
                              {...field}
                              type="number"
                              step="1"
                              placeholder="—"
                              data-testid="input-max-daily-profit"
                              className="font-mono"
                              value={field.value as string | number}
                            />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      </FieldRow>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="breakEvenPts"
                    render={({ field }) => (
                      <FieldRow
                        label="Break Even (ticks)"
                        desc="Optional — move SL to entry when profit reaches this"
                      >
                        <FormItem>
                          <FormControl>
                            <Input
                              {...field}
                              type="number"
                              step="1"
                              placeholder="—"
                              data-testid="input-break-even"
                              className="font-mono"
                              value={field.value as string | number}
                            />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      </FieldRow>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="cancelPendingAfterBars"
                    render={({ field }) => (
                      <FieldRow
                        label="Cancel Pending (bars)"
                        desc="Optional — cancel pending orders after N bars unfilled"
                      >
                        <FormItem>
                          <FormControl>
                            <Input
                              {...field}
                              type="number"
                              step="1"
                              placeholder="—"
                              data-testid="input-cancel-pending"
                              className="font-mono"
                              value={field.value as string | number}
                            />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      </FieldRow>
                    )}
                  />
                </CardContent>
              </Card>

              <div className="flex gap-3 pb-4">
                <Button
                  type="submit"
                  data-testid="button-save-config"
                  disabled={isMutating}
                  className="flex items-center gap-2"
                >
                  <Save className="h-4 w-4" />
                  {isMutating ? "Saving..." : isCreating ? "Create Symbol" : "Save Changes"}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  data-testid="button-cancel-config"
                  onClick={() => setSheetOpen(false)}
                  className="flex items-center gap-2"
                >
                  <X className="h-4 w-4" />
                  Cancel
                </Button>
              </div>
            </form>
          </Form>
        </SheetContent>
      </Sheet>

      {/* Integrações */}
      <div className="space-y-3">
        <h2 className="text-lg font-semibold tracking-tight">Integrações</h2>
        <Card className="border-border bg-card">
          <CardHeader className="pb-3">
            <div className="flex items-center gap-3">
              <MessageSquare className="h-5 w-5 text-indigo-400" />
              <div className="flex-1">
                <CardTitle className="text-sm font-semibold">Discord</CardTitle>
                <CardDescription className="text-xs mt-0.5">
                  Receba notificações de ordens, entradas, fechamentos e limite diário no Discord.
                </CardDescription>
              </div>
              <Switch
                checked={botSettings?.discordEnabled ?? false}
                onCheckedChange={toggleDiscord}
                disabled={updateSettings.isPending || !botSettings?.discordWebhookConfigured}
              />
            </div>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="flex items-center gap-2 text-xs">
              {botSettings?.discordWebhookConfigured ? (
                <>
                  <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
                  <span className="text-muted-foreground">
                    Webhook configurado via <span className="font-mono">DISCORD_WEBHOOK_URL</span>
                  </span>
                </>
              ) : (
                <>
                  <XCircle className="h-3.5 w-3.5 text-red-500" />
                  <span className="text-muted-foreground">
                    Webhook não configurado — defina{" "}
                    <span className="font-mono">DISCORD_WEBHOOK_URL</span> no <span className="font-mono">.env</span> ou no <span className="font-mono">start-local.bat</span>
                  </span>
                </>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      <AlertDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {(() => {
                const cfg = configs?.find((c) => c.id === deleteTarget);
                return cfg ? `Remove ${cfg.symbol} — ${STRATEGY_OPTIONS.find((s) => s.value === cfg.strategyName)?.label ?? cfg.strategyName}?` : "Remove configuration?";
              })()}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {(() => {
                const cfg = configs?.find((c) => c.id === deleteTarget);
                return cfg
                  ? <>This will permanently delete the <span className="font-mono font-semibold">{cfg.strategyName}</span> configuration for <span className="font-mono font-semibold">{cfg.symbol}</span>. This action cannot be undone.</>
                  : "This action cannot be undone.";
              })()}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="btn-cancel-delete">Cancel</AlertDialogCancel>
            <AlertDialogAction
              data-testid="btn-confirm-delete"
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => {
                if (deleteTarget != null) {
                  deleteConfig.mutate({ id: deleteTarget });
                  setDeleteTarget(null);
                }
              }}
            >
              Remove
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
