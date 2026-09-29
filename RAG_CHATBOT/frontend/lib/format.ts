const compactFormatter = new Intl.NumberFormat("vi-VN", {
  notation: "compact",
  maximumFractionDigits: 1,
});

const fullFormatter = new Intl.NumberFormat("vi-VN", {
  maximumFractionDigits: 0,
});

export function formatCompact(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—";
  }

  return compactFormatter.format(value);
}

export function formatFull(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—";
  }

  return fullFormatter.format(value);
}

export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—";
  }

  return `${value.toFixed(1)}%`;
}

export function formatMonthKey(value: number | string): string {
  const text = String(value);

  if (text.length !== 8) {
    return text;
  }

  return `${text.slice(4, 6)}/${text.slice(0, 4)}`;
}
