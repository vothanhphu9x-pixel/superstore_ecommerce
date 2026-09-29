"use client";

import { useEffect, useMemo, useState } from "react";

import {
  ApiError,
  DashboardMetric,
  DashboardRange,
  dashboardService,
} from "@/lib/api";

interface MetricState<T> {
  key: string;
  data: T | null;
  cached: boolean;
  error: string | null;
}

export function useMetric<T>(
  metric: DashboardMetric,
  range: DashboardRange,
  limit?: number,
) {
  const requestKey = useMemo(
    () => [metric, range.month_from, range.month_to, limit ?? ""].join("|"),
    [metric, range.month_from, range.month_to, limit],
  );

  const [state, setState] = useState<MetricState<T>>({
    key: "",
    data: null,
    cached: false,
    error: null,
  });

  useEffect(() => {
    let cancelled = false;

    dashboardService
      .get<T>(metric, range, limit)
      .then((response) => {
        if (cancelled) {
          return;
        }

        setState({
          key: requestKey,
          data: response.data,
          cached: response.cached,
          error: null,
        });
      })
      .catch((error: unknown) => {
        if (cancelled) {
          return;
        }

        const message =
          error instanceof ApiError ? error.message : "Không tải được dữ liệu.";

        setState({
          key: requestKey,
          data: null,
          cached: false,
          error: message,
        });
      });

    return () => {
      cancelled = true;
    };
  }, [limit, metric, range, requestKey]);

  const settled = state.key === requestKey;

  return {
    data: settled ? state.data : null,
    cached: settled ? state.cached : false,
    error: settled ? state.error : null,
    loading: !settled,
  };
}
