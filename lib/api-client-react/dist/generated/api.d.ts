import type { QueryKey, UseMutationOptions, UseMutationResult, UseQueryOptions, UseQueryResult } from "@tanstack/react-query";
import type { BotConfig, BotConfigInput, BotStatus, BotSummary, ErrorResponse, HealthStatus, ListTradesParams, Trade } from "./api.schemas";
import { customFetch } from "../custom-fetch";
import type { ErrorType, BodyType } from "../custom-fetch";
type AwaitedInput<T> = PromiseLike<T> | T;
type Awaited<O> = O extends AwaitedInput<infer T> ? T : never;
type SecondParameter<T extends (...args: never) => unknown> = Parameters<T>[1];
/**
 * Returns server health status
 * @summary Health check
 */
export declare const getHealthCheckUrl: () => string;
export declare const healthCheck: (options?: RequestInit) => Promise<HealthStatus>;
export declare const getHealthCheckQueryKey: () => readonly ["/api/healthz"];
export declare const getHealthCheckQueryOptions: <TData = Awaited<ReturnType<typeof healthCheck>>, TError = ErrorType<unknown>>(options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof healthCheck>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}) => UseQueryOptions<Awaited<ReturnType<typeof healthCheck>>, TError, TData> & {
    queryKey: QueryKey;
};
export type HealthCheckQueryResult = NonNullable<Awaited<ReturnType<typeof healthCheck>>>;
export type HealthCheckQueryError = ErrorType<unknown>;
/**
 * @summary Health check
 */
export declare function useHealthCheck<TData = Awaited<ReturnType<typeof healthCheck>>, TError = ErrorType<unknown>>(options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof healthCheck>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}): UseQueryResult<TData, TError> & {
    queryKey: QueryKey;
};
/**
 * Returns all per-symbol bot configurations ordered by symbol name
 * @summary List all symbol configurations
 */
export declare const getListSymbolConfigsUrl: () => string;
export declare const listSymbolConfigs: (options?: RequestInit) => Promise<BotConfig[]>;
export declare const getListSymbolConfigsQueryKey: () => readonly ["/api/bot/configs"];
export declare const getListSymbolConfigsQueryOptions: <TData = Awaited<ReturnType<typeof listSymbolConfigs>>, TError = ErrorType<unknown>>(options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof listSymbolConfigs>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}) => UseQueryOptions<Awaited<ReturnType<typeof listSymbolConfigs>>, TError, TData> & {
    queryKey: QueryKey;
};
export type ListSymbolConfigsQueryResult = NonNullable<Awaited<ReturnType<typeof listSymbolConfigs>>>;
export type ListSymbolConfigsQueryError = ErrorType<unknown>;
/**
 * @summary List all symbol configurations
 */
export declare function useListSymbolConfigs<TData = Awaited<ReturnType<typeof listSymbolConfigs>>, TError = ErrorType<unknown>>(options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof listSymbolConfigs>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}): UseQueryResult<TData, TError> & {
    queryKey: QueryKey;
};
/**
 * @summary Create a new symbol configuration
 */
export declare const getCreateSymbolConfigUrl: () => string;
export declare const createSymbolConfig: (botConfigInput: BotConfigInput, options?: RequestInit) => Promise<BotConfig>;
export declare const getCreateSymbolConfigMutationOptions: <TError = ErrorType<ErrorResponse>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof createSymbolConfig>>, TError, {
        data: BodyType<BotConfigInput>;
    }, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationOptions<Awaited<ReturnType<typeof createSymbolConfig>>, TError, {
    data: BodyType<BotConfigInput>;
}, TContext>;
export type CreateSymbolConfigMutationResult = NonNullable<Awaited<ReturnType<typeof createSymbolConfig>>>;
export type CreateSymbolConfigMutationBody = BodyType<BotConfigInput>;
export type CreateSymbolConfigMutationError = ErrorType<ErrorResponse>;
/**
 * @summary Create a new symbol configuration
 */
export declare const useCreateSymbolConfig: <TError = ErrorType<ErrorResponse>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof createSymbolConfig>>, TError, {
        data: BodyType<BotConfigInput>;
    }, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationResult<Awaited<ReturnType<typeof createSymbolConfig>>, TError, {
    data: BodyType<BotConfigInput>;
}, TContext>;
/**
 * @summary Get configuration for a specific symbol
 */
export declare const getGetSymbolConfigUrl: (symbol: string) => string;
export declare const getSymbolConfig: (symbol: string, options?: RequestInit) => Promise<BotConfig>;
export declare const getGetSymbolConfigQueryKey: (symbol: string) => readonly [`/api/bot/configs/${string}`];
export declare const getGetSymbolConfigQueryOptions: <TData = Awaited<ReturnType<typeof getSymbolConfig>>, TError = ErrorType<ErrorResponse>>(symbol: string, options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof getSymbolConfig>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}) => UseQueryOptions<Awaited<ReturnType<typeof getSymbolConfig>>, TError, TData> & {
    queryKey: QueryKey;
};
export type GetSymbolConfigQueryResult = NonNullable<Awaited<ReturnType<typeof getSymbolConfig>>>;
export type GetSymbolConfigQueryError = ErrorType<ErrorResponse>;
/**
 * @summary Get configuration for a specific symbol
 */
export declare function useGetSymbolConfig<TData = Awaited<ReturnType<typeof getSymbolConfig>>, TError = ErrorType<ErrorResponse>>(symbol: string, options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof getSymbolConfig>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}): UseQueryResult<TData, TError> & {
    queryKey: QueryKey;
};
/**
 * @summary Update configuration for a specific symbol
 */
export declare const getUpdateSymbolConfigUrl: (symbol: string) => string;
export declare const updateSymbolConfig: (symbol: string, botConfigInput: BotConfigInput, options?: RequestInit) => Promise<BotConfig>;
export declare const getUpdateSymbolConfigMutationOptions: <TError = ErrorType<ErrorResponse>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof updateSymbolConfig>>, TError, {
        symbol: string;
        data: BodyType<BotConfigInput>;
    }, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationOptions<Awaited<ReturnType<typeof updateSymbolConfig>>, TError, {
    symbol: string;
    data: BodyType<BotConfigInput>;
}, TContext>;
export type UpdateSymbolConfigMutationResult = NonNullable<Awaited<ReturnType<typeof updateSymbolConfig>>>;
export type UpdateSymbolConfigMutationBody = BodyType<BotConfigInput>;
export type UpdateSymbolConfigMutationError = ErrorType<ErrorResponse>;
/**
 * @summary Update configuration for a specific symbol
 */
export declare const useUpdateSymbolConfig: <TError = ErrorType<ErrorResponse>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof updateSymbolConfig>>, TError, {
        symbol: string;
        data: BodyType<BotConfigInput>;
    }, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationResult<Awaited<ReturnType<typeof updateSymbolConfig>>, TError, {
    symbol: string;
    data: BodyType<BotConfigInput>;
}, TContext>;
/**
 * @summary Delete configuration for a specific symbol
 */
export declare const getDeleteSymbolConfigUrl: (symbol: string) => string;
export declare const deleteSymbolConfig: (symbol: string, options?: RequestInit) => Promise<void>;
export declare const getDeleteSymbolConfigMutationOptions: <TError = ErrorType<ErrorResponse>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof deleteSymbolConfig>>, TError, {
        symbol: string;
    }, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationOptions<Awaited<ReturnType<typeof deleteSymbolConfig>>, TError, {
    symbol: string;
}, TContext>;
export type DeleteSymbolConfigMutationResult = NonNullable<Awaited<ReturnType<typeof deleteSymbolConfig>>>;
export type DeleteSymbolConfigMutationError = ErrorType<ErrorResponse>;
/**
 * @summary Delete configuration for a specific symbol
 */
export declare const useDeleteSymbolConfig: <TError = ErrorType<ErrorResponse>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof deleteSymbolConfig>>, TError, {
        symbol: string;
    }, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationResult<Awaited<ReturnType<typeof deleteSymbolConfig>>, TError, {
    symbol: string;
}, TContext>;
/**
 * @summary Update configuration by numeric database ID
 */
export declare const getUpdateSymbolConfigByIdUrl: (id: number) => string;
export declare const updateSymbolConfigById: (id: number, botConfigInput: BodyType<BotConfigInput>, options?: RequestInit) => Promise<BotConfig>;
export declare const getUpdateSymbolConfigByIdMutationOptions: <TError = ErrorType<ErrorResponse>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof updateSymbolConfigById>>, TError, {
        id: number;
        data: BodyType<BotConfigInput>;
    }, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationOptions<Awaited<ReturnType<typeof updateSymbolConfigById>>, TError, {
    id: number;
    data: BodyType<BotConfigInput>;
}, TContext>;
export type UpdateSymbolConfigByIdMutationResult = NonNullable<Awaited<ReturnType<typeof updateSymbolConfigById>>>;
export type UpdateSymbolConfigByIdMutationBody = BodyType<BotConfigInput>;
export type UpdateSymbolConfigByIdMutationError = ErrorType<ErrorResponse>;
/**
 * @summary Update configuration by numeric database ID
 */
export declare const useUpdateSymbolConfigById: <TError = ErrorType<ErrorResponse>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof updateSymbolConfigById>>, TError, {
        id: number;
        data: BodyType<BotConfigInput>;
    }, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationResult<Awaited<ReturnType<typeof updateSymbolConfigById>>, TError, {
    id: number;
    data: BodyType<BotConfigInput>;
}, TContext>;
/**
 * @summary Delete configuration by numeric database ID
 */
export declare const getDeleteSymbolConfigByIdUrl: (id: number) => string;
export declare const deleteSymbolConfigById: (id: number, options?: RequestInit) => Promise<void>;
export declare const getDeleteSymbolConfigByIdMutationOptions: <TError = ErrorType<ErrorResponse>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof deleteSymbolConfigById>>, TError, {
        id: number;
    }, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationOptions<Awaited<ReturnType<typeof deleteSymbolConfigById>>, TError, {
    id: number;
}, TContext>;
export type DeleteSymbolConfigByIdMutationResult = NonNullable<Awaited<ReturnType<typeof deleteSymbolConfigById>>>;
export type DeleteSymbolConfigByIdMutationError = ErrorType<ErrorResponse>;
/**
 * @summary Delete configuration by numeric database ID
 */
export declare const useDeleteSymbolConfigById: <TError = ErrorType<ErrorResponse>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof deleteSymbolConfigById>>, TError, {
        id: number;
    }, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationResult<Awaited<ReturnType<typeof deleteSymbolConfigById>>, TError, {
    id: number;
}, TContext>;
/**
 * Backward-compatible alias for GET /bot/configs. Returns the first configuration ordered by symbol.
 * @summary Get bot configuration (legacy — returns first symbol's config)
 */
export declare const getGetBotConfigUrl: () => string;
export declare const getBotConfig: (options?: RequestInit) => Promise<BotConfig>;
export declare const getGetBotConfigQueryKey: () => readonly ["/api/bot/config"];
export declare const getGetBotConfigQueryOptions: <TData = Awaited<ReturnType<typeof getBotConfig>>, TError = ErrorType<unknown>>(options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof getBotConfig>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}) => UseQueryOptions<Awaited<ReturnType<typeof getBotConfig>>, TError, TData> & {
    queryKey: QueryKey;
};
export type GetBotConfigQueryResult = NonNullable<Awaited<ReturnType<typeof getBotConfig>>>;
export type GetBotConfigQueryError = ErrorType<unknown>;
/**
 * @summary Get bot configuration (legacy — returns first symbol's config)
 */
export declare function useGetBotConfig<TData = Awaited<ReturnType<typeof getBotConfig>>, TError = ErrorType<unknown>>(options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof getBotConfig>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}): UseQueryResult<TData, TError> & {
    queryKey: QueryKey;
};
/**
 * Backward-compatible alias for PUT /bot/configs/{symbol}. Updates the first configuration ordered by symbol.
 * @summary Update bot configuration (legacy — updates first symbol's config)
 */
export declare const getUpdateBotConfigUrl: () => string;
export declare const updateBotConfig: (botConfigInput: BotConfigInput, options?: RequestInit) => Promise<BotConfig>;
export declare const getUpdateBotConfigMutationOptions: <TError = ErrorType<unknown>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof updateBotConfig>>, TError, {
        data: BodyType<BotConfigInput>;
    }, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationOptions<Awaited<ReturnType<typeof updateBotConfig>>, TError, {
    data: BodyType<BotConfigInput>;
}, TContext>;
export type UpdateBotConfigMutationResult = NonNullable<Awaited<ReturnType<typeof updateBotConfig>>>;
export type UpdateBotConfigMutationBody = BodyType<BotConfigInput>;
export type UpdateBotConfigMutationError = ErrorType<unknown>;
/**
 * @summary Update bot configuration (legacy — updates first symbol's config)
 */
export declare const useUpdateBotConfig: <TError = ErrorType<unknown>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof updateBotConfig>>, TError, {
        data: BodyType<BotConfigInput>;
    }, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationResult<Awaited<ReturnType<typeof updateBotConfig>>, TError, {
    data: BodyType<BotConfigInput>;
}, TContext>;
/**
 * @summary Get current bot status and stats
 */
export declare const getGetBotStatusUrl: () => string;
export declare const getBotStatus: (options?: RequestInit) => Promise<BotStatus>;
export declare const getGetBotStatusQueryKey: () => readonly ["/api/bot/status"];
export declare const getGetBotStatusQueryOptions: <TData = Awaited<ReturnType<typeof getBotStatus>>, TError = ErrorType<unknown>>(options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof getBotStatus>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}) => UseQueryOptions<Awaited<ReturnType<typeof getBotStatus>>, TError, TData> & {
    queryKey: QueryKey;
};
export type GetBotStatusQueryResult = NonNullable<Awaited<ReturnType<typeof getBotStatus>>>;
export type GetBotStatusQueryError = ErrorType<unknown>;
/**
 * @summary Get current bot status and stats
 */
export declare function useGetBotStatus<TData = Awaited<ReturnType<typeof getBotStatus>>, TError = ErrorType<unknown>>(options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof getBotStatus>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}): UseQueryResult<TData, TError> & {
    queryKey: QueryKey;
};
/**
 * @summary List all trades
 */
export declare const getListTradesUrl: (params?: ListTradesParams) => string;
export declare const listTrades: (params?: ListTradesParams, options?: RequestInit) => Promise<Trade[]>;
export declare const getListTradesQueryKey: (params?: ListTradesParams) => readonly ["/api/bot/trades", ...ListTradesParams[]];
export declare const getListTradesQueryOptions: <TData = Awaited<ReturnType<typeof listTrades>>, TError = ErrorType<unknown>>(params?: ListTradesParams, options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof listTrades>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}) => UseQueryOptions<Awaited<ReturnType<typeof listTrades>>, TError, TData> & {
    queryKey: QueryKey;
};
export type ListTradesQueryResult = NonNullable<Awaited<ReturnType<typeof listTrades>>>;
export type ListTradesQueryError = ErrorType<unknown>;
/**
 * @summary List all trades
 */
export declare function useListTrades<TData = Awaited<ReturnType<typeof listTrades>>, TError = ErrorType<unknown>>(params?: ListTradesParams, options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof listTrades>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}): UseQueryResult<TData, TError> & {
    queryKey: QueryKey;
};
/**
 * @summary Get a specific trade
 */
export declare const getGetTradeUrl: (id: number) => string;
export declare const getTrade: (id: number, options?: RequestInit) => Promise<Trade>;
export declare const getGetTradeQueryKey: (id: number) => readonly [`/api/bot/trades/${number}`];
export declare const getGetTradeQueryOptions: <TData = Awaited<ReturnType<typeof getTrade>>, TError = ErrorType<unknown>>(id: number, options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof getTrade>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}) => UseQueryOptions<Awaited<ReturnType<typeof getTrade>>, TError, TData> & {
    queryKey: QueryKey;
};
export type GetTradeQueryResult = NonNullable<Awaited<ReturnType<typeof getTrade>>>;
export type GetTradeQueryError = ErrorType<unknown>;
/**
 * @summary Get a specific trade
 */
export declare function useGetTrade<TData = Awaited<ReturnType<typeof getTrade>>, TError = ErrorType<unknown>>(id: number, options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof getTrade>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}): UseQueryResult<TData, TError> & {
    queryKey: QueryKey;
};
/**
 * @summary Get bot performance summary
 */
export declare const getGetBotSummaryUrl: () => string;
export declare const getBotSummary: (options?: RequestInit) => Promise<BotSummary>;
export declare const getGetBotSummaryQueryKey: () => readonly ["/api/bot/summary"];
export declare const getGetBotSummaryQueryOptions: <TData = Awaited<ReturnType<typeof getBotSummary>>, TError = ErrorType<unknown>>(options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof getBotSummary>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}) => UseQueryOptions<Awaited<ReturnType<typeof getBotSummary>>, TError, TData> & {
    queryKey: QueryKey;
};
export type GetBotSummaryQueryResult = NonNullable<Awaited<ReturnType<typeof getBotSummary>>>;
export type GetBotSummaryQueryError = ErrorType<unknown>;
/**
 * @summary Get bot performance summary
 */
export declare function useGetBotSummary<TData = Awaited<ReturnType<typeof getBotSummary>>, TError = ErrorType<unknown>>(options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof getBotSummary>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}): UseQueryResult<TData, TError> & {
    queryKey: QueryKey;
};
export {};
//# sourceMappingURL=api.d.ts.map