import { Boxes, Gauge, IndianRupee, Package, ShieldAlert, Warehouse } from "lucide-react";
import { EmptyState } from "../../components/EmptyState";
import { KpiCard } from "../../components/KpiCard";
import type { PredictiveOverview } from "../../types/api";
import { formatNumber, formatPaise } from "../../utils/format";

export function PredictiveKpiStrip({ overview }: { overview: PredictiveOverview | null }) {
  if (!overview?.ready) {
    return (
      <EmptyState
        title="Forecasts unavailable"
        message={
          overview?.note ||
          overview?.kpis?.expected_demand_units?.unavailable_reason ||
          "Persisted demand forecasts are missing for this cohort. Predictive views stay empty until forecasts exist."
        }
      />
    );
  }

  const kpis = overview.kpis;
  const horizon = overview.horizon_days ?? 28;

  return (
    <div className="grid-kpi-6 predictive-kpi-strip">
      <KpiCard
        label="Expected demand"
        icon={<Boxes size={16} />}
        value={kpis?.expected_demand_units?.value == null ? "N/A" : formatNumber(Math.round(kpis.expected_demand_units.value))}
        sublabel={kpis?.expected_demand_units?.label ?? `Next ${horizon} days · forecast as-of ${overview.forecast_as_of ?? "?"}`}
      />
      <KpiCard
        label="Stockout risk SKUs"
        icon={<ShieldAlert size={16} />}
        tone="warn"
        value={kpis?.products_at_stockout_risk?.value == null ? "N/A" : formatNumber(kpis.products_at_stockout_risk.value)}
        sublabel={kpis?.products_at_stockout_risk?.definition ?? "Count at elevated risk — not a summed probability."}
      />
      <KpiCard
        label="Excess inventory (proxy)"
        icon={<Warehouse size={16} />}
        value={kpis?.excess_inventory_value_paise?.value == null ? "N/A" : formatPaise(kpis.excess_inventory_value_paise.value)}
        sublabel={kpis?.excess_inventory_value_paise?.definition ?? "Forecast cover proxy — distinct from modeled excess risk."}
      />
      <KpiCard
        label="Recommended spend"
        icon={<IndianRupee size={16} />}
        value={
          kpis?.recommended_replenishment_spend_paise?.value == null
            ? "N/A"
            : formatPaise(kpis.recommended_replenishment_spend_paise.value)
        }
        sublabel={kpis?.recommended_replenishment_spend_paise?.definition ?? "Open optimizer recommendations."}
      />
      <KpiCard
        label="Projected inventory value"
        icon={<Package size={16} />}
        value={kpis?.projected_inventory_value_paise?.value == null ? "N/A" : formatPaise(kpis.projected_inventory_value_paise.value)}
        sublabel={
          kpis?.projected_inventory_value_paise?.definition ??
          `Policy: ${kpis?.projected_inventory_value_paise?.policy ?? "no_reorder"}. Current ${formatPaise(kpis?.projected_inventory_value_paise?.current_inventory_value_paise ?? overview.live_inventory_value_paise)}`
        }
      />
      <KpiCard
        label="Forecast coverage"
        icon={<Gauge size={16} />}
        value={kpis?.forecast_coverage?.label ?? `${kpis?.forecast_coverage?.covered ?? 0} / ${kpis?.forecast_coverage?.selected ?? 0}`}
        sublabel="SKUs with persisted daily forecast for the selected horizon."
      />
    </div>
  );
}
