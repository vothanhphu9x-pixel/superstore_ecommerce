"use client";

import { useState } from "react";

import { useStaffSession } from "@/components/auth/StaffSessionProvider";
import type { DashboardMetric, DashboardRange } from "@/lib/api";

import BreakdownChart from "./BreakdownChart";
import KpiRow from "./KpiRow";
import RangeFilter from "./RangeFilter";
import RevenueTrendChart from "./RevenueTrendChart";

const DEFAULT_RANGE: DashboardRange = {
  month_from: 20230101,
  month_to: 20271201,
};

export default function DashboardView() {
  const [range, setRange] = useState(DEFAULT_RANGE);
  const staff = useStaffSession();

  function canView(metric: DashboardMetric): boolean {
    return staff.metrics.includes(metric);
  }

  const canViewKpi = canView("kpi");
  const canViewRevenueTrend = canView("revenue-trend");
  const canViewCategory = canView("by-category");
  const canViewRegion = canView("by-region");
  const canViewTopProducts = canView("top-products");

  const hasVisibleMetric =
    canViewKpi ||
    canViewRevenueTrend ||
    canViewCategory ||
    canViewRegion ||
    canViewTopProducts;

  return (
    <main className="mx-auto flex max-w-7xl flex-col gap-5 px-4 py-6 md:px-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-indigo-600">
            Superstore Analytics
          </p>

          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-slate-950">
            Dashboard kinh doanh
          </h1>

          <p className="mt-1 text-sm text-slate-500">
            Snowflake Gold/Mart · FastAPI · Redis cache
          </p>
        </div>

        {hasVisibleMetric ? (
          <RangeFilter value={range} onChange={setRange} />
        ) : null}
      </header>

      {!hasVisibleMetric ? (
        <section className="rounded-xl border border-slate-200 bg-white px-6 py-10 text-center shadow-sm">
          <h2 className="text-lg font-semibold text-slate-900">
            Chưa có dashboard phù hợp
          </h2>

          <p className="mt-2 text-sm text-slate-500">
            Role <strong>{staff.role}</strong> hiện chưa được cấp quyền xem các
            metric của dashboard này.
          </p>
        </section>
      ) : null}

      {canViewKpi ? <KpiRow range={range} /> : null}

      {canViewRevenueTrend ? <RevenueTrendChart range={range} /> : null}

      {canViewCategory || canViewRegion ? (
        <div className="grid gap-5 lg:grid-cols-2">
          {canViewCategory ? (
            <BreakdownChart
              metric="by-category"
              range={range}
              title="Doanh thu theo nhóm hàng"
              categoryKey="CATEGORY"
            />
          ) : null}

          {canViewRegion ? (
            <BreakdownChart
              metric="by-region"
              range={range}
              title="Doanh thu theo khu vực"
              categoryKey="REGION"
            />
          ) : null}
        </div>
      ) : null}

      {canViewTopProducts ? (
        <BreakdownChart
          metric="top-products"
          range={range}
          title="Top 10 sản phẩm"
          description="Gộp theo product_id, không tách theo phiên bản SCD2."
          categoryKey="PRODUCT_NAME"
          limit={10}
        />
      ) : null}
    </main>
  );
}
