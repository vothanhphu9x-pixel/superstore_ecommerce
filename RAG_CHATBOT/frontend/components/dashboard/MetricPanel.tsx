"use client";

export default function MetricPanel({
  title,
  description,
  loading,
  error,
  empty,
  cached,
  children,
  className = "",
}: {
  title: string;
  description?: string;
  loading: boolean;
  error: string | null;
  empty: boolean;
  cached?: boolean;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      className={[
        "rounded-2xl border border-slate-200",
        "bg-white p-5 shadow-sm",
        className,
      ].join(" ")}
    >
      <header className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h2 className="font-semibold text-slate-950">{title}</h2>

          {description ? (
            <p className="mt-1 text-sm text-slate-500">{description}</p>
          ) : null}
        </div>

        {cached ? (
          <span className="rounded-full bg-emerald-50 px-2 py-1 text-xs text-emerald-700">
            Redis cache
          </span>
        ) : null}
      </header>

      {loading ? (
        <div
          className="h-64 animate-pulse rounded-xl bg-slate-100"
          aria-label="Đang tải dữ liệu"
        />
      ) : error ? (
        <div
          className="flex h-64 items-center justify-center rounded-xl bg-red-50 p-6 text-center text-sm text-red-700"
          role="alert"
        >
          {error}
        </div>
      ) : empty ? (
        <div className="flex h-64 items-center justify-center rounded-xl bg-slate-50 text-sm text-slate-500">
          Không có dữ liệu trong kỳ đã chọn.
        </div>
      ) : (
        children
      )}
    </section>
  );
}
