import { useCallback, useEffect, useState } from "react";
import { fetchOrderHistory } from "../api/client";
import { classifyError, type AppError } from "../utils/errors";
import type { OrderRecord } from "../types";

type HistoryStatus = "idle" | "loading" | "success" | "error";

export function useOrderHistory(autoFetch = true) {
  const [orders, setOrders] = useState<OrderRecord[]>([]);
  const [status, setStatus] = useState<HistoryStatus>("idle");
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setStatus("loading");
    setError(null);
    try {
      const data = await fetchOrderHistory();
      setOrders(data);
      setStatus("success");
    } catch (err) {
      const appError: AppError =
        err && typeof err === "object" && "title" in err
          ? (err as AppError)
          : classifyError(err instanceof Error ? err.message : "Failed to load orders");
      setError(appError.message);
      setStatus("error");
    }
  }, []);

  useEffect(() => {
    if (autoFetch) refresh();
  }, [autoFetch, refresh]);

  const completedCount = orders.filter((o) => o.status === "complete").length;
  const failedCount = orders.filter((o) => o.status === "failed").length;
  const processingCount = orders.filter((o) => o.status === "processing").length;

  return {
    orders,
    status,
    error,
    refresh,
    completedCount,
    failedCount,
    processingCount,
    isLoading: status === "loading" && orders.length === 0,
    isRefreshing: status === "loading" && orders.length > 0,
  };
}
