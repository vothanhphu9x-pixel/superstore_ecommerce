"use client";

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { DashboardRange, RevenueTrendRow } from "@/lib/api";
import { formatCompact, formatFull, formatMonthKey } from "@/lib/format";

import MetricPanel from "./MetricPanel";
import { useMetric } from "./useMetric";

export default function RevenueTrendChart({
  range,
}: {
  range: DashboardRange;
}) {
  const { data, loading, error, cached } = useMetric<RevenueTrendRow[]>(
    "revenue-trend",
    range,
  );

  return (
    <MetricPanel
      title="Doanh thu theo tháng"
      description="Doanh thu và lợi nhuận gộp từ mart_revenue_monthly."
      loading={loading}
      error={error}
      empty={!data?.length}
      cached={cached}
    >
      <div className="h-72 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={data ?? []}
            margin={{
              top: 8,
              right: 16,
              bottom: 8,
              left: 8,
            }}
          >
            <CartesianGrid vertical={false} stroke="#e2e8f0" />

            <XAxis
              dataKey="MONTH_DATE_KEY"
              tickFormatter={formatMonthKey}
              tickLine={false}
              axisLine={false}
            />

            <YAxis
              tickFormatter={formatCompact}
              tickLine={false}
              axisLine={false}
              width={62}
            />

            <Tooltip
              labelFormatter={(value) => formatMonthKey(Number(value))}
              formatter={(value, name) => [
                formatFull(Number(value)),
                name === "REVENUE" ? "Doanh thu" : "Lợi nhuận gộp",
              ]}
            />

            <Legend
              formatter={(value) =>
                value === "REVENUE" ? "Doanh thu" : "Lợi nhuận gộp"
              }
            />

            <Line
              type="monotone"
              dataKey="REVENUE"
              stroke="#4f46e5"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4 }}
            />

            <Line
              type="monotone"
              dataKey="GROSS_PROFIT"
              stroke="#ea580c"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </MetricPanel>
  );
}
