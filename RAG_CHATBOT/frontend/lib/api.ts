const INTERNAL_API_ROOT = "/api/internal";

export type DashboardMetric =
  | "kpi"
  | "revenue-trend"
  | "by-category"
  | "by-region"
  | "top-products";

export interface DashboardRange {
  month_from: number;
  month_to: number;
}

export interface DashboardResponse<T> {
  metric: DashboardMetric;
  month_from: number;
  month_to: number;
  row_count: number;
  data: T;
  cached: boolean;
}

export interface KpiData {
  REVENUE: number | null;
  GROSS_PROFIT: number | null;
  ORDERS: number | null;
  AVG_ORDER_VALUE: number | null;
  MARGIN_PCT: number | null;
}

export interface RevenueTrendRow {
  MONTH_DATE_KEY: number;
  REVENUE: number;
  COGS: number;
  GROSS_PROFIT: number;
}

export interface BreakdownRow {
  [key: string]: string | number | null;
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function detailFromPayload(payload: unknown, fallback: string): string {
  if (payload && typeof payload === "object" && "detail" in payload) {
    const detail = (
      payload as {
        detail?: unknown;
      }
    ).detail;

    if (typeof detail === "string") {
      return detail;
    }

    if (Array.isArray(detail)) {
      return detail
        .map((item) => {
          if (item && typeof item === "object" && "msg" in item) {
            return String(item.msg);
          }

          return JSON.stringify(item);
        })
        .join("; ");
    }
  }

  return fallback;
}

async function getJson<T>(url: string, context: string): Promise<T> {
  let response: Response;

  try {
    response = await fetch(url, {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
      cache: "no-store",
      credentials: "same-origin",
    });
  } catch {
    throw new ApiError(`${context}: không kết nối được Next server.`, 0);
  }

  const payload: unknown = await response.json().catch(() => null);

  if (!response.ok) {
    throw new ApiError(
      `${context}: ${detailFromPayload(
        payload,
        `máy chủ trả lỗi ${response.status}`,
      )}`,
      response.status,
    );
  }

  return payload as T;
}

export const dashboardService = {
  async get<T>(
    metric: DashboardMetric,
    range: DashboardRange,
    limit?: number,
  ): Promise<DashboardResponse<T>> {
    const params = new URLSearchParams({
      month_from: String(range.month_from),
      month_to: String(range.month_to),
    });

    if (limit !== undefined) {
      params.set("limit", String(limit));
    }

    return getJson<DashboardResponse<T>>(
      `${INTERNAL_API_ROOT}/dashboard/${metric}?${params}`,
      `Dashboard [${metric}]`,
    );
  },
};
