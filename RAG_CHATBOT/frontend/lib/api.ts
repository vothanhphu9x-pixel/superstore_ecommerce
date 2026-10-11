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

/*
 * Staff authentication types
 */

export type StaffRole =
  | "admin"
  | "analyst"
  | "ceo"
  | "cfo"
  | "sales"
  | "marketing"
  | "warehouse"
  | "plant";

export interface StaffProfile {
  email: string;
  name: string;
  role: StaffRole;
  metrics: DashboardMetric[];
}

export interface StaffLoginInput {
  email: string;
  password: string;
}

export interface StaffLogoutResponse {
  detail: string;
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

async function requestJson<T>(
  url: string,
  context: string,
  init: RequestInit,
): Promise<T> {
  let response: Response;

  const headers = new Headers(init.headers);

  headers.set("Accept", "application/json");

  /*
   * Login dùng JSON body. Không ghi đè nếu caller đã tự
   * thiết lập một Content-Type khác.
   */
  if (init.body !== undefined && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  try {
    response = await fetch(url, {
      ...init,
      headers,
      cache: "no-store",

      /*
       * Cho phép browser gửi cookie superstore_staff tới
       * các API route cùng origin.
       */
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

function getJson<T>(url: string, context: string): Promise<T> {
  return requestJson<T>(url, context, {
    method: "GET",
  });
}

function postJson<T>(url: string, context: string, body?: unknown): Promise<T> {
  return requestJson<T>(url, context, {
    method: "POST",
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

/*
 * Dashboard API
 */

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

/*
 * Staff authentication API
 */

export const staffService = {
  login(input: StaffLoginInput): Promise<StaffProfile> {
    return postJson<StaffProfile>(
      `${INTERNAL_API_ROOT}/staff/login`,
      "Đăng nhập",
      input,
    );
  },

  me(): Promise<StaffProfile> {
    return getJson<StaffProfile>(
      `${INTERNAL_API_ROOT}/staff/me`,
      "Staff session",
    );
  },

  async logout(): Promise<void> {
    await postJson<StaffLogoutResponse>(
      `${INTERNAL_API_ROOT}/staff/logout`,
      "Đăng xuất",
    );
  },
};
