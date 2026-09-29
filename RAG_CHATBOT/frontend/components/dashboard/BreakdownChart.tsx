"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { BreakdownRow, DashboardMetric, DashboardRange } from "@/lib/api";
import { formatCompact, formatFull } from "@/lib/format";

import MetricPanel from "./MetricPanel";
import { useMetric } from "./useMetric";

export default function BreakdownChart({
  metric,
  range,
  title,
  description,
  categoryKey,
  limit,
}: {
  metric: DashboardMetric;
  range: DashboardRange;
  title: string;
  description?: string;
  categoryKey: string;
  limit?: number;
}) {
  const { data, loading, error, cached } = useMetric<BreakdownRow[]>(
    metric,
    range,
    limit,
  );

  const height = Math.max(260, (data?.length ?? 0) * 38);

  return (
    <MetricPanel
      title={title}
      description={description}
      loading={loading}
      error={error}
      empty={!data?.length}
      cached={cached}
    >
      <div className="w-full" style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data ?? []}
            layout="vertical"
            margin={{
              top: 4,
              right: 20,
              bottom: 4,
              left: 24,
            }}
          >
            <CartesianGrid horizontal={false} stroke="#e2e8f0" />

            <XAxis
              type="number"
              dataKey="REVENUE"
              tickFormatter={formatCompact}
              tickLine={false}
              axisLine={false}
            />

            <YAxis
              type="category"
              dataKey={categoryKey}
              width={140}
              tickLine={false}
              axisLine={false}
              tickFormatter={(value: string) =>
                value.length > 22 ? `${value.slice(0, 21)}…` : value
              }
            />

            <Tooltip
              formatter={(value) => [formatFull(Number(value)), "Doanh thu"]}
            />

            <Bar
              dataKey="REVENUE"
              fill="#4f46e5"
              radius={[0, 5, 5, 0]}
              maxBarSize={24}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </MetricPanel>
  );
}
