const INR = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 0,
});

const INR_DECIMAL = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 2,
});

const NUM = new Intl.NumberFormat("en-IN");

export function formatPaise(paise: number | null | undefined): string {
  if (paise == null || Number.isNaN(paise)) return "N/A";
  return INR.format(paise / 100);
}

export function formatPaiseDecimal(paise: number | null | undefined): string {
  if (paise == null || Number.isNaN(paise)) return "N/A";
  return INR_DECIMAL.format(paise / 100);
}

export function formatNumber(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "N/A";
  return NUM.format(n);
}

export function formatPercent(
  value: number | null | undefined,
  digits = 1,
): string {
  if (value == null || Number.isNaN(value)) return "N/A";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(digits)}%`;
}

export function formatLatencyMs(ms: number | null | undefined): string {
  if (ms == null || Number.isNaN(ms)) return "Not measured";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(2)} s`;
}

export const NOT_MEASURED = "Not measured";
