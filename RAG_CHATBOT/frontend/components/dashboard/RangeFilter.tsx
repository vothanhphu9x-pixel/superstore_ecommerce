"use client";

import { DashboardRange } from "@/lib/api";

const PRESETS: Array<{
  label: string;
  range: DashboardRange;
}> = [
  {
    label: "Tất cả",
    range: {
      month_from: 20230101,
      month_to: 20271201,
    },
  },
  {
    label: "2023",
    range: {
      month_from: 20230101,
      month_to: 20231201,
    },
  },
  {
    label: "2024",
    range: {
      month_from: 20240101,
      month_to: 20241201,
    },
  },
  {
    label: "2025",
    range: {
      month_from: 20250101,
      month_to: 20251201,
    },
  },
  {
    label: "2026",
    range: {
      month_from: 20260101,
      month_to: 20261201,
    },
  },
];

export default function RangeFilter({
  value,
  onChange,
}: {
  value: DashboardRange;
  onChange: (range: DashboardRange) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="mr-1 text-sm text-slate-500">Kỳ báo cáo</span>

      {PRESETS.map(({ label, range }) => {
        const active =
          value.month_from === range.month_from &&
          value.month_to === range.month_to;

        return (
          <button
            key={label}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(range)}
            className={[
              "rounded-lg border px-3 py-1.5 text-sm",
              "transition-colors focus:outline-none",
              "focus-visible:ring-2 focus-visible:ring-indigo-500",
              active
                ? "border-indigo-600 bg-indigo-600 text-white"
                : "border-slate-300 bg-white text-slate-700 hover:bg-slate-50",
            ].join(" ")}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}
