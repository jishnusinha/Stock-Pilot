import { DataTable } from "../../components/DataTable";
import { EmptyState } from "../../components/EmptyState";
import type { PredictiveRisks } from "../../types/api";
import { formatNumber, formatPaise } from "../../utils/format";

export function ExcessInventoryPanel({
  data,
  onSelectProduct,
}: {
  data: PredictiveRisks | null;
  onSelectProduct: (id: number) => void;
}) {
  const excess = data?.excess;
  const items = excess?.items ?? [];

  return (
    <section className="card excess-panel">
      <h2 className="card-title">Excess inventory signals</h2>
      <p className="card-sub">
        <strong>Cover proxy:</strong> {excess?.proxy_definition ?? "Operational cover vs forecast demand."}
      </p>
      <p className="card-sub">
        <strong>Modeled excess risk:</strong> {excess?.modeled_risk_definition ?? "From Excess Risk Agent on recommendations — not merged with the proxy."}
      </p>
      {!data?.ready ? (
        <EmptyState title="Excess ranking unavailable" message="Risk endpoint did not return excess items." />
      ) : items.length === 0 ? (
        <EmptyState title="No excess candidates" message="No SKUs met excess proxy rules in this filter." />
      ) : (
        <DataTable
          rows={items}
          onSelect={(row) => onSelectProduct(row.product_id)}
          columns={[
            { key: "product", header: "Product", render: (row) => `${row.name} · ${row.sku}` },
            { key: "proxy", header: "Proxy excess value", align: "right", render: (row) => formatPaise(row.excess_value_paise_proxy) },
            { key: "units", header: "Proxy units", align: "right", render: (row) => formatNumber(row.excess_units_proxy) },
            { key: "modeled", header: "Modeled excess risk", align: "right", render: (row) => (row.modeled_excess_risk == null ? "N/A" : `${(row.modeled_excess_risk * 100).toFixed(0)}%`) },
            { key: "dos", header: "Days of supply", align: "right", render: (row) => (row.days_of_supply == null ? "N/A" : row.days_of_supply.toFixed(0)) },
          ]}
        />
      )}
    </section>
  );
}
