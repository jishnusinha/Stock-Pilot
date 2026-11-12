import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
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
import { api } from "../api/client";
import { ChartCard } from "../components/ChartCard";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { KpiCard } from "../components/KpiCard";
import { useDebouncedValue } from "../hooks/useApi";
import type { ProductRow, SimulateResponse } from "../types/api";
import { formatDate } from "../utils/dates";
import { formatNumber, formatPaise } from "../utils/format";

export function Simulator() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const initialProduct = params.get("product") ? Number(params.get("product")) : null;

  const [products, setProducts] = useState<ProductRow[]>([]);
  const [productId, setProductId] = useState<number | null>(initialProduct);
  const [qty, setQty] = useState(12);
  const [pricePaise, setPricePaise] = useState(0);
  const [leadDays, setLeadDays] = useState(7);
  const [budgetPaise, setBudgetPaise] = useState(50_000_000); // ₹5,00,000
  const [scenarioName, setScenarioName] = useState("");

  const [result, setResult] = useState<SimulateResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const debouncedInputs = useDebouncedValue(
    { productId, qty, pricePaise, leadDays, budgetPaise },
    350,
  );

  const [catalogError, setCatalogError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setCatalogError(null);
    // Load full catalog (API allows page_size up to 250)
    api
      .products({ page: 1, page_size: 250, sort: "sku" })
      .then((r) => {
        if (cancelled) return;
        setProducts(r.items);
        if (!r.items.length) {
          setCatalogError("No products returned from API.");
          return;
        }
        setProductId((prev) => {
          if (prev && r.items.some((p) => p.id === prev)) return prev;
          const fromUrl =
            initialProduct && r.items.find((p) => p.id === initialProduct);
          const pick = fromUrl ?? r.items[0];
          if (pick) {
            setPricePaise(
              pick.unit_price_paise && pick.unit_price_paise > 0
                ? pick.unit_price_paise
                : 10000,
            );
            setQty(defaultOrderQty(pick));
            return pick.id;
          }
          return prev;
        });
      })
      .catch((e: Error) => {
        if (cancelled) return;
        setProducts([]);
        setCatalogError(e.message || "Failed to load products");
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- load catalog once
  }, []);

  useEffect(() => {
    if (!initialProduct) return;
    setProductId(initialProduct);
    const p = products.find((x) => x.id === initialProduct);
    if (p?.unit_price_paise && p.unit_price_paise > 0) setPricePaise(p.unit_price_paise);
  }, [initialProduct, products]);

  useEffect(() => {
    const pid = debouncedInputs.productId;
    const price = debouncedInputs.pricePaise;
    if (!pid || !price || price <= 0) return;
    abortRef.current?.abort();
    const ac = new AbortController();
    abortRef.current = ac;
    setLoading(true);
    setError(null);
    api
      .simulate(
        {
          product_id: pid,
          reorder_qty: Math.max(0, Math.round(debouncedInputs.qty)),
          proposed_price_paise: Math.round(price),
          lead_time_days: debouncedInputs.leadDays,
          budget_paise: Math.max(0, Math.round(debouncedInputs.budgetPaise)),
        },
        ac.signal,
      )
      .then((res) => {
        if (!ac.signal.aborted) setResult(res);
      })
      .catch((e: Error) => {
        if (ac.signal.aborted || e.name === "AbortError") return;
        setError(e.message);
        setResult(null);
      })
      .finally(() => {
        if (!ac.signal.aborted) setLoading(false);
      });
    return () => ac.abort();
  }, [debouncedInputs]);

  const selected = products.find((p) => p.id === productId);
  const purchaseCost = (result?.proposed_metrics.purchase_cost_paise ?? 0);
  const overBudget = purchaseCost > budgetPaise && qty > 0;

  async function saveScenario() {
    if (!productId || !scenarioName.trim()) return;
    await api.saveScenario({
      name: scenarioName,
      product_id: productId,
      inputs: {
        product_id: productId,
        reorder_qty: qty,
        proposed_price_paise: pricePaise,
        lead_time_days: leadDays,
        budget_paise: budgetPaise,
      },
      results: result ?? undefined,
    });
    alert("Scenario saved.");
  }

  async function applyReorder() {
    if (!productId || overBudget) return;
    const orderQty = Math.max(1, Math.round(qty > 0 ? qty : defaultOrderQty(selected)));
    try {
      await api.createReorder({
        product_id: productId,
        qty: orderQty,
        notes: `What-If draft · lead ${leadDays}d · price ₹${(pricePaise / 100).toFixed(2)}`,
      });
      navigate("/reorders");
    } catch (e) {
      alert(e instanceof Error ? e.message : "Failed to create reorder draft");
    }
  }

  const chartData = mergeSeries(result);

  return (
    <>
      <header className="page-header">
        <h1>What-If Simulator</h1>
        <p className="subtitle">
          Compare baseline vs proposed plan · 28-day horizon · SIMULATED_SUPPLY outcomes
        </p>
      </header>

      <PickerRow>
        <label style={{ flex: 1 }}>
          Product
          <select
            className="select"
            value={productId ?? ""}
            onChange={(e) => {
              const id = Number(e.target.value);
              setProductId(id);
              setResult(null);
              const p = products.find((x) => x.id === id);
              if (p?.unit_price_paise && p.unit_price_paise > 0) {
                setPricePaise(p.unit_price_paise);
              }
              if (p) setQty(defaultOrderQty(p));
            }}
            style={{ marginTop: 8 }}
            disabled={!products.length}
          >
            {!products.length ? (
              <option value="">
                {catalogError ? "Failed to load products" : "Loading products…"}
              </option>
            ) : null}
            {products.map((p) => (
              <option key={p.id} value={p.id}>
                {p.sku} — {p.name}
              </option>
            ))}
          </select>
        </label>
      </PickerRow>
      {catalogError ? (
        <div style={{ marginBottom: 16 }}>
          <ErrorState message={catalogError} />
        </div>
      ) : null}

      <div className="grid-kpi-4">
        <KpiCard
          label="Stockout days (proposed)"
          value={fmtMetric(result?.proposed_metrics.stockout_days)}
        />
        <KpiCard
          label="Revenue (proposed)"
          value={formatPaise(result?.proposed_metrics.revenue_paise)}
        />
        <KpiCard
          label="Purchase cost"
          value={formatPaise(purchaseCost)}
          sublabel={overBudget ? "Exceeds budget" : "Within budget"}
        />
        <KpiCard
          label="Gross margin"
          value={formatPaise(result?.proposed_metrics.gross_margin_paise)}
        />
      </div>

      <div className="grid-2-1">
        <section className="card">
          <h2 className="card-title">Scenario controls</h2>
          <SliderField
            label={`Reorder quantity${selected?.pack_size ? ` (pack ${selected.pack_size})` : ""}`}
            value={qty}
            min={0}
            max={500}
            step={Math.max(1, selected?.pack_size ?? 12)}
            onChange={setQty}
          />
          <SliderField
            label={`Selling price (${formatPaise(pricePaise)})`}
            value={pricePaise / 100}
            min={Math.max(1, (selected?.unit_price_paise ?? 10000) / 100 / 2)}
            max={((selected?.unit_price_paise ?? 10000) / 100) * 2}
            step={1}
            onChange={(v) => setPricePaise(Math.round(v * 100))}
          />
          <SliderField label="Lead time (days)" value={leadDays} min={1} max={30} onChange={setLeadDays} />
          <SliderField
            label={`Budget (${formatPaise(budgetPaise)})`}
            value={budgetPaise / 100}
            min={0}
            max={500000}
            step={1000}
            onChange={(v) => setBudgetPaise(Math.round(v * 100))}
          />
          {result?.arrival_date ? (
            <p style={{ fontSize: 13, color: "var(--color-text-muted)" }}>
              Expected arrival: {formatDate(result.arrival_date)} (lead time scenario)
            </p>
          ) : null}
        </section>

        <ChartCard
          title="Projected inventory"
          subtitle={`${result?.baseline_label ?? "Baseline"} vs ${result?.proposed_label ?? "Proposed"}`}
        >
          {error ? (
            <ErrorState message={error} />
          ) : !chartData.length ? (
            <EmptyState title={loading ? "Computing…" : "No simulation"} message="Select a product and adjust sliders." />
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={(d) => formatDate(d).slice(0, 6)} />
                <YAxis width={40} tick={{ fontSize: 10 }} />
                <Tooltip labelFormatter={(l) => formatDate(String(l))} />
                <Legend />
                <Line dataKey="baseline" stroke="var(--color-text-muted)" dot={false} name="Baseline" />
                <Line dataKey="proposed" stroke="var(--color-primary)" dot={false} name="Proposed" />
              </LineChart>
            </ResponsiveContainer>
          )}
        </ChartCard>
      </div>

      <section className="card" style={{ marginBottom: 16 }}>
        <h2 className="card-title">Outcome comparison</h2>
        <ComparisonTable result={result} />
      </section>

      <div style={{ display: "flex", flexWrap: "wrap", gap: 12, alignItems: "flex-end" }}>
        <label>
          Scenario name
          <input className="input" value={scenarioName} onChange={(e) => setScenarioName(e.target.value)} style={{ marginTop: 8, width: 220 }} />
        </label>
        <button type="button" className="btn btn-secondary" onClick={() => saveScenario().catch((e) => alert(e.message))}>
          Save scenario
        </button>
        <button
          type="button"
          className="btn btn-primary"
          disabled={overBudget || !productId}
          title={
            overBudget
              ? "Proposed purchase exceeds budget"
              : !productId
                ? "Select a product"
                : qty < 1
                  ? "Will use pack size if qty is 0"
                  : undefined
          }
          onClick={() => applyReorder().catch((e) => alert(e.message))}
        >
          Create draft reorder
        </button>
        <button type="button" className="btn btn-secondary" onClick={() => navigate("/reorders")}>
          View reorders
        </button>
      </div>
    </>
  );
}

function SliderField({
  label,
  value,
  min,
  max,
  step = 1,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  onChange: (v: number) => void;
}) {
  return (
    <div style={{ marginBottom: 16 }}>
      <label style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 6 }}>
        <span>{label}</span>
        <span className="tabular">{formatNumber(value)}</span>
      </label>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        style={{ width: "100%" }}
        aria-valuemin={min}
        aria-valuemax={max}
        aria-valuenow={value}
      />
    </div>
  );
}

function mergeSeries(result: SimulateResponse | null) {
  if (!result) return [];
  const map = new Map<string, { date: string; baseline?: number; proposed?: number }>();
  result.baseline_series.forEach((p) => {
    map.set(p.date, { date: p.date, baseline: p.inventory, proposed: map.get(p.date)?.proposed });
  });
  result.proposed_series.forEach((p) => {
    const cur = map.get(p.date) ?? { date: p.date };
    cur.proposed = p.inventory;
    map.set(p.date, cur);
  });
  return [...map.values()].sort((a, b) => a.date.localeCompare(b.date));
}

function ComparisonTable({ result }: { result: SimulateResponse | null }) {
  const rows = result?.comparison_rows ?? defaultComparison(result);
  return (
    <table style={{ width: "100%", fontSize: 13, borderCollapse: "collapse" }}>
      <thead>
        <tr style={{ borderBottom: "1px solid var(--color-border)", textAlign: "left" }}>
          <th style={{ padding: 8 }}>Metric</th>
          <th style={{ padding: 8 }}>Baseline</th>
          <th style={{ padding: 8 }}>Proposed</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.metric} style={{ borderBottom: "1px solid var(--color-border)" }}>
            <td style={{ padding: 8 }}>{r.metric}</td>
            <td className="tabular" style={{ padding: 8 }}>
              {String(r.baseline)}
            </td>
            <td className="tabular" style={{ padding: 8 }}>
              {String(r.proposed)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function defaultComparison(result: SimulateResponse | null) {
  if (!result) return [];
  return [
    {
      metric: "Stockout days",
      baseline: fmtMetric(result.baseline_metrics.stockout_days),
      proposed: fmtMetric(result.proposed_metrics.stockout_days),
    },
    {
      metric: "Unmet demand (units)",
      baseline: fmtMetric(result.baseline_metrics.unmet_demand_units),
      proposed: fmtMetric(result.proposed_metrics.unmet_demand_units),
    },
    {
      metric: "Stockout probability",
      baseline: fmtProb(result.baseline_metrics.stockout_probability),
      proposed: fmtProb(result.proposed_metrics.stockout_probability),
    },
    {
      metric: "Revenue",
      baseline: formatPaise(result.baseline_metrics.revenue_paise),
      proposed: formatPaise(result.proposed_metrics.revenue_paise),
    },
  ];
}

function fmtMetric(v: number | null | undefined) {
  if (v == null || Number.isNaN(v)) return "N/A";
  return formatNumber(v);
}

function fmtProb(v: number | null | undefined) {
  if (v == null || Number.isNaN(v)) return "N/A";
  return `${(v * 100).toFixed(1)}%`;
}

function PickerRow({ children }: { children: React.ReactNode }) {
  return <div style={{ marginBottom: 16, display: "flex", gap: 12 }}>{children}</div>;
}

function defaultOrderQty(product: ProductRow | null | undefined): number {
  if (!product) return 12;
  const pack = Math.max(1, product.pack_size ?? 12);
  const point = product.reorder_point ?? pack;
  // nearest pack multiple at/above reorder point
  return Math.max(pack, Math.ceil(point / pack) * pack);
}
