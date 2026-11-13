import type { AnalyticsMonth, MovementReport, RankedProduct } from "../../types/api";
import type { AnalyticsQuery } from "../../utils/analyticsQuery";
import { formatNumber, formatPaise } from "../../utils/format";
import { compactPaise, isPartialMonth } from "./utils";

export function selectMonth(month: string, update: (partial: Partial<AnalyticsQuery>) => void) {
  const [year, mon] = month.split("-");
  update({ year, month: String(Number(mon)), from: undefined, to: undefined });
}

export function pickMonth(state: { activeLabel?: string | number } | null, update: (partial: Partial<AnalyticsQuery>) => void) {
  if (state?.activeLabel) selectMonth(String(state.activeLabel), update);
}

export function TurnoverSpark({ months }: { months: AnalyticsMonth[] }) {
  const values = months.map((month) => month.turnover).filter((value): value is number => value != null && Number.isFinite(value));
  if (values.length < 2) return <span className="note">No monthly trend in this filter.</span>;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const width = 120;
  const height = 36;
  const points = values
    .map((value, index) => {
      const x = (index / (values.length - 1)) * width;
      const y = height - ((value - min) / span) * (height - 4) - 2;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg className="spark" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`Monthly turnover from ${values[0].toFixed(2)} to ${values[values.length - 1].toFixed(2)}`}>
      <polyline fill="none" stroke="var(--color-primary)" strokeWidth="2" points={points} />
    </svg>
  );
}

export function MonthTip({ active, payload }: { active?: boolean; payload?: Array<{ payload: AnalyticsMonth }> }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  const partial = isPartialMonth(row.days);
  return (
    <div className="chart-tip">
      <strong>{row.month}</strong>
      {partial ? <div>Partial month ({row.days} days in cohort)</div> : null}
      <div>Inventory value {formatPaise(row.inventory_value_paise)}</div>
      <div>Previous month {row.previous_inventory_value_paise == null ? "N/A" : formatPaise(row.previous_inventory_value_paise)}</div>
      <div>Change {row.absolute_change_paise == null ? "N/A" : formatPaise(row.absolute_change_paise)}</div>
      <div>Percent {row.percent_change == null ? "N/A" : `${row.percent_change.toFixed(1)}%`}</div>
      <div>Fulfilled revenue {formatPaise(row.revenue_paise)}</div>
      <div>Ratio {row.inventory_to_sales == null ? "N/A" : row.inventory_to_sales.toFixed(2)}</div>
    </div>
  );
}

export function monthBarFill(row: AnalyticsMonth, selectedMonth: string): string {
  if (row.month === selectedMonth) return "var(--color-forecast)";
  return "var(--color-primary)";
}

export function monthBarOpacity(row: AnalyticsMonth): number {
  return isPartialMonth(row.days) ? 0.55 : 1;
}

export function TurnoverTip({ active, payload }: { active?: boolean; payload?: Array<{ payload: AnalyticsMonth }> }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="chart-tip">
      <strong>{row.month}</strong>
      <div>Turns {row.turnover == null ? "N/A" : row.turnover.toFixed(2)}</div>
      <div>COGS {formatPaise(row.cogs_paise)}</div>
      <div>Average inventory {formatPaise(row.average_inventory_value_paise)}</div>
    </div>
  );
}

export function RankTip({ active, payload, mode }: { active?: boolean; payload?: Array<{ payload: RankedProduct }>; mode: "value" | "quantity" }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="chart-tip">
      <strong>{row.name}</strong>
      <div>{row.sku}</div>
      <div>{mode === "value" ? formatPaise(row.inventory_value_paise) : `${formatNumber(row.stock_units)} units`}</div>
    </div>
  );
}

export function SalesTip({ active, payload }: { active?: boolean; payload?: Array<{ payload: AnalyticsMonth }> }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="chart-tip">
      <strong>{row.month}</strong>
      {isPartialMonth(row.days) ? <div>Partial month</div> : null}
      <div>Inventory value {formatPaise(row.inventory_value_paise)}</div>
      <div>Fulfilled revenue {formatPaise(row.revenue_paise)}</div>
      <div>Ratio {row.inventory_to_sales == null ? "N/A" : row.inventory_to_sales.toFixed(2)}</div>
    </div>
  );
}

type FlowStep = { name: string; base: number; span: number; amount: number; kind: "total" | "up" | "down" };

export function waterfallSteps(report: MovementReport): FlowStep[] {
  let cursor = 0;
  const rows: FlowStep[] = [];
  function total(name: string, value: number) {
    rows.push({ name, base: 0, span: Math.max(value, 0), amount: value, kind: "total" });
    cursor = value;
  }
  function delta(name: string, amount: number) {
    const next = cursor + amount;
    rows.push({ name, base: Math.min(cursor, next), span: Math.abs(amount), amount, kind: amount >= 0 ? "up" : "down" });
    cursor = next;
  }
  const split = report.reconciliation_receipt_units != null || report.reconciliation_writeoff_units != null;
  const reconIn = report.reconciliation_receipt_units ?? 0;
  const reconOut = report.reconciliation_writeoff_units ?? 0;
  total("Opening", report.opening_units ?? 0);
  delta(split ? "Replenishment" : "Receipts", report.routine_receipts_units ?? report.receipts_units ?? 0);
  if (split) delta("Reconcile in", reconIn);
  delta("Returns", report.returns_units ?? 0);
  delta("Adjustments", report.adjustments_units ?? 0);
  delta("Sales", -(report.fulfilled_sales_units ?? 0));
  delta(split ? "Write-offs" : "Write-offs", -((report.routine_writeoff_units ?? report.writeoff_units ?? 0)));
  if (split) delta("Reconcile out", -reconOut);
  total("Closing", report.closing_units ?? 0);
  return rows;
}

export function WaterfallTip({ active, payload }: { active?: boolean; payload?: Array<{ payload: FlowStep }> }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="chart-tip">
      <strong>{row.name}</strong>
      <div>{formatNumber(row.amount)} units</div>
    </div>
  );
}

export function AbcRow({
  abc,
  cells,
  selected,
  onSelect,
}: {
  abc: string;
  cells: import("../../types/api").AbcCell[];
  selected?: string;
  onSelect: (cell: string) => void;
}) {
  return (
    <>
      <strong className="abc-head">{abc}</strong>
      {["X", "Y", "Z"].map((xyz) => {
        const cell = cells.find((row) => row.cell === `${abc}${xyz}`);
        const key = `${abc}${xyz}`;
        return (
          <button
            key={key}
            type="button"
            className={`abc-cell${selected === key ? " selected" : ""}`}
            aria-pressed={selected === key}
            onClick={() => onSelect(key)}
          >
            <strong>{key}</strong>
            <span>{cell?.sku_count ?? 0} SKUs</span>
            <span>{formatPaise(cell?.inventory_value_paise)}</span>
            <span>{cell?.value_share == null ? "N/A" : `${(cell.value_share * 100).toFixed(1)}%`}</span>
          </button>
        );
      })}
    </>
  );
}

export { compactPaise };
