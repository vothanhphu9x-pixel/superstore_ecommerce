"use client";

import { DashboardRange, KpiData } from "@/lib/api";
import { formatFull, formatPercent } from "@/lib/format";

import { useMetric } from "./useMetric";

const KPI_ITEMS: Array<{
  key: keyof KpiData;
  label: string;
  format: (value: number | null) => string;
}> = [
  {
    key: "REVENUE",
    label: "Doanh thu",
    format: formatFull,
  },
  {
    key: "GROSS_PROFIT",
    label: "Lợi nhuận gộp",
    format: formatFull,
  },
  {
    key: "MARGIN_PCT",
    label: "Biên lợi nhuận",
    format: formatPercent,
  },
  {
    key: "ORDERS",
    label: "Số đơn",
    format: formatFull,
  },
  {
    key: "AVG_ORDER_VALUE",
    label: "Giá trị đơn trung bình",
    format: formatFull,
  },
];

export default function KpiRow({ range }: { range: DashboardRange }) {
  const { data, loading, error, cached } = useMetric<KpiData>("kpi", range);

  if (error) {
    return (
      <div
        className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700"
        role="alert"
      >
        {error}
      </div>
    );
  }

  return (
    <section>
      <div className="mb-2 flex justify-end">
        {cached ? (
          <span className="text-xs text-emerald-700">
            Dữ liệu lấy từ Redis cache
          </span>
        ) : null}
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {KPI_ITEMS.map((item) => (
          <article
            key={item.key}
            className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
          >
            <p className="text-sm text-slate-500">{item.label}</p>

            {loading ? (
              <div className="mt-3 h-8 w-28 animate-pulse rounded bg-slate-100" />
            ) : (
              <p className="mt-2 text-2xl font-semibold tabular-nums text-slate-950">
                {item.format(data?.[item.key] ?? null)}
              </p>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}
