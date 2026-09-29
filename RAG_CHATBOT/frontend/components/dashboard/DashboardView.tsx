"use client";

import { useState } from "react";

import { DashboardRange } from "@/lib/api";

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

  return (
    <main className="mx-auto flex max-w-7xl flex-col gap-5 px-4 py-6 md:px-6">
      <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
        Local preview: dashboard chưa có staff authentication. Không public
        deploy trước STEP 7.
      </div>

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

        <RangeFilter value={range} onChange={setRange} />
      </header>

      <KpiRow range={range} />

      <RevenueTrendChart range={range} />

      <div className="grid gap-5 lg:grid-cols-2">
        <BreakdownChart
          metric="by-category"
          range={range}
          title="Doanh thu theo nhóm hàng"
          categoryKey="CATEGORY"
        />

        <BreakdownChart
          metric="by-region"
          range={range}
          title="Doanh thu theo khu vực"
          categoryKey="REGION"
        />
      </div>

      <BreakdownChart
        metric="top-products"
        range={range}
        title="Top 10 sản phẩm"
        description="Gộp theo product_id, không tách theo phiên bản SCD2."
        categoryKey="PRODUCT_NAME"
        limit={10}
      />
    </main>
  );
}
