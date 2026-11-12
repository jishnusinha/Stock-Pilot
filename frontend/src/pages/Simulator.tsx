import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
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
import { PageHeader, SliderControl } from "../components/Controls";
import { useToast } from "../components/Toast";
import { useDebouncedValue } from "../hooks/useApi";
import type { ProductRow, ScenarioSummary, SimulateResponse } from "../types/api";
import { formatDate, formatDateTime } from "../utils/dates";
import { formatNumber, formatPaise } from "../utils/format";

export function Simulator() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const toast = useToast();
  const initialProduct = params.get("product") ? Number(params.get("product")) : null;

  const [products, setProducts] = useState<ProductRow[]>([]);
  const [productId, setProductId] = useState<number | null>(initialProduct);
  const [qty, setQty] = useState(12);
  const [pricePaise, setPricePaise] = useState(0);
  const [leadDays, setLeadDays] = useState(7);
  const [budgetPaise, setBudgetPaise] = useState(50_000_000);
  const [scenarioName, setScenarioName] = useState("");
  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([]);
  const [saved, setSaved] = useState<SimulateResponse | null>(null);
  const [savedLabel, setSavedLabel] = useState<string | null>(null);

  const [result, setResult] = useState<SimulateResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const debouncedInputs = useDebouncedValue({ productId, qty, pricePaise, leadDays, budgetPaise }, 350);

  function refreshScenarios() {
    api.listScenarios().then(setScenarios).catch(() => setScenarios([]));
  }

  useEffect(() => {
    let cancelled = false;
    api
      .products({ page: 1, page_size: 250, sort: "name", direction: "asc" })
      .then((r) => {
        if (cancelled) return;
        setProducts(r.items);
        if (!r.items.length) {
          setCatalogError("No products returned from the API.");
          return;
        }
        setProductId((prev) => {
          if (prev && r.items.some((p) => p.id === prev)) return prev;
          const pick = (initialProduct && r.items.find((p) => p.id === initialProduct)) || r.items[0];
          if (pick) {
            setPricePaise(pick.unit_price_paise && pick.unit_price_paise > 0 ? pick.unit_price_paise : 10000);
            setQty(defaultOrderQty(pick));
            return pick.id;
          }
          return prev;
        });
      })
      .catch((e: Error) => {
        if (!cancelled) setCatalogError(e.message || "Failed to load products");
      });
    refreshScenarios();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!initialProduct) return;
    setProductId(initialProduct);
  }, [initialProduct]);

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
  const purchaseCost = result?.proposed_metrics.purchase_cost_paise ?? 0;
  const overBudget = purchaseCost > budgetPaise && qty > 0;
  const chartData = useMemo(() => mergeSeries(result), [result]);
  const shelf = selected?.unit_price_paise && selected.unit_price_paise > 0 ? selected.unit_price_paise : 10000;

  async function saveScenario() {
    if (!productId) return;
    if (!scenarioName.trim()) {
      toast.error("Name the scenario before saving.");
      return;
    }
    setSaving(true);
    try {
      await api.saveScenario({
        name: scenarioName.trim(),
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
      toast.success("Scenario saved. Reopen it from the list.");
      setSaved(result);
      setSavedLabel(scenarioName.trim());
      refreshScenarios();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not save scenario");
    } finally {
      setSaving(false);
    }
  }

  async function reopen(id: number) {
    try {
      const detail = await api.getScenario(id);
      const inputs = detail.inputs;
      setProductId(detail.product_id);
      if (typeof inputs.reorder_qty === "number") setQty(inputs.reorder_qty);
      if (typeof inputs.proposed_price_paise === "number") setPricePaise(inputs.proposed_price_paise);
      if (typeof inputs.lead_time_days === "number") setLeadDays(inputs.lead_time_days);
      if (typeof inputs.budget_paise === "number") setBudgetPaise(inputs.budget_paise);
      setScenarioName(detail.name || "");
      const stored = detail.results;
      if (stored && stored.proposed_metrics && stored.baseline_series && stored.proposed_series) {
        setSaved(stored as SimulateResponse);
        setSavedLabel(detail.name || `Scenario ${detail.id}`);
      } else {
        setSaved(null);
        setSavedLabel(detail.name || `Scenario ${detail.id}`);
      }
      toast.success("Scenario inputs restored. The chart will recompute.");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not open scenario");
    }
  }

  async function applyReorder() {
    if (!productId || overBudget) return;
    const applied = result?.applied_qty;
    if (applied === 0) {
      toast.error("Applied quantity is 0 under the budget and pack-size rules. No draft was created.");
      return;
    }
    const orderQty = applied != null && applied > 0 ? applied : Math.max(1, Math.round(qty > 0 ? qty : defaultOrderQty(selected)));
    try {
      await api.createReorder({
        product_id: productId,
        qty: orderQty,
        notes: `What-if draft · lead ${leadDays}d · price ₹${(pricePaise / 100).toFixed(2)} · applied ${orderQty}`,
      });
      toast.success("Draft reorder created. Approving it will not increase stock.");
      navigate("/reorders");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to create reorder draft");
    }
  }

  const base = result?.baseline_metrics;
  const prop = result?.proposed_metrics;

  return (
    <>
      <PageHeader
        title="What-If Simulator"
        subtitle="Compare a proposed order against the current plan. Price response is an observational association, not causal elasticity. Figures are simulated."
        actions={
          <select
            className="select"
            style={{ minWidth: 220, width: "auto" }}
            aria-label="Product"
            value={productId ?? ""}
            disabled={!products.length}
            onChange={(e) => {
              const id = Number(e.target.value);
              setProductId(id);
              setResult(null);
              const p = products.find((x) => x.id === id);
              if (p?.unit_price_paise && p.unit_price_paise > 0) setPricePaise(p.unit_price_paise);
              if (p) setQty(defaultOrderQty(p));
            }}
          >
            {!products.length ? <option value="">{catalogError ? "Catalog unavailable" : "Loading products…"}</option> : null}
            {products.map((p) => (
              <option key={p.id} value={p.id}>
                {p.sku} — {p.name}
              </option>
            ))}
          </select>
        }
      />
      {catalogError ? <ErrorState message={catalogError} /> : null}

      <div className="grid-kpi-4">
        <KpiCard
          label="Projected revenue"
          value={formatPaise(prop?.revenue_paise)}
          sublabel={deltaText(base?.revenue_paise, prop?.revenue_paise, true)}
        />
        <KpiCard
          label="Stockout risk"
          tone="risk"
          value={fmtProb(prop?.stockout_probability)}
          sublabel={probDelta(base?.stockout_probability, prop?.stockout_probability)}
        />
        <KpiCard
          label="Purchase cost"
          tone="info"
          value={formatPaise(prop?.purchase_cost_paise)}
          sublabel={overBudget ? "Exceeds the budget you set" : "Proposed order cash"}
        />
        <KpiCard
          label="Gross margin proxy"
          value={formatPaise(prop?.gross_margin_paise)}
          sublabel="Revenue minus unit cost × units. Not cash profit."
        />
      </div>

      <div className="sim-layout">
        <section className="card">
          <h2 className="card-title">Scenario controls</h2>
          <p className="card-sub" style={{ marginBottom: 12 }}>
            {selected ? `${selected.name} · pack ${selected.pack_size ?? "—"} · shelf ${formatPaise(shelf)}` : "Select a product"}
          </p>
          <SliderControl
            label="Reorder quantity"
            value={qty}
            min={0}
            max={Math.max(240, (selected?.pack_size ?? 12) * 20)}
            step={Math.max(1, selected?.pack_size ?? 1)}
            display={`${formatNumber(qty)} units`}
            minLabel="0"
            maxLabel="max"
            onChange={setQty}
          />
          <SliderControl
            label="Proposed selling price"
            value={pricePaise / 100}
            min={Math.max(1, Math.round(shelf / 100 / 2))}
            max={Math.max(2, Math.round((shelf / 100) * 2))}
            step={1}
            display={formatPaise(pricePaise)}
            minLabel="lower"
            maxLabel="higher"
            onChange={(v) => setPricePaise(Math.round(v * 100))}
          />
          <p className="note">Price effect is observational. It is not a proven elasticity.</p>
          <SliderControl
            label="Supplier lead time"
            value={leadDays}
            min={1}
            max={30}
            display={`${leadDays} days`}
            minLabel="1d"
            maxLabel="30d"
            onChange={setLeadDays}
          />
          <SliderControl
            label="Purchasing budget"
            value={budgetPaise / 100}
            min={0}
            max={500000}
            step={1000}
            display={formatPaise(budgetPaise)}
            minLabel="₹0"
            maxLabel="₹5L"
            onChange={(v) => setBudgetPaise(Math.round(v * 100))}
          />
          {result?.applied_qty != null ? (
            <p className="note">
              Requested {formatNumber(result.requested_qty ?? qty)} → applied <strong>{formatNumber(result.applied_qty)}</strong>
              {result.qty_normalization_note ? ` (${result.qty_normalization_note})` : ""}
            </p>
          ) : null}
          {result?.price_effect ? (
            <p className="note">
              Stored price association: Δ {result.price_effect.units_delta != null ? result.price_effect.units_delta.toFixed(2) : "—"} units/day.
            </p>
          ) : null}
        </section>

        <ChartCard
          title="Projected inventory"
          subtitle={`${result?.baseline_label ?? "Current plan"} vs ${result?.proposed_label ?? "proposal"} · 28 days · deterministic paths, not intervals`}
        >
          {error ? (
            <ErrorState message={error} />
          ) : !chartData.length ? (
            <EmptyState title={loading ? "Computing scenario…" : "No simulation yet"} message="Choose a product. Results update as you move the controls." />
          ) : (
            <ResponsiveContainer width="100%" height={320}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={(d) => formatDate(String(d)).slice(0, 6)} minTickGap={16} />
                <YAxis width={40} tick={{ fontSize: 10 }} />
                <Tooltip labelFormatter={(l) => formatDate(String(l))} />
                <Legend />
                <ReferenceLine y={0} stroke="var(--color-risk)" strokeDasharray="4 4" label={{ value: "Stockout", fontSize: 11, fill: "var(--color-risk)" }} />
                {result?.arrival_date ? (
                  <ReferenceLine x={result.arrival_date} stroke="var(--color-primary)" strokeDasharray="3 3" label={{ value: "Arrival", fontSize: 11, fill: "var(--color-primary)" }} />
                ) : null}
                <Line dataKey="baseline" stroke="#7d8b84" strokeWidth={2} dot={false} name="Current plan" />
                <Line dataKey="proposed" stroke="var(--color-primary)" strokeWidth={2.4} dot={false} name="Proposed" />
              </LineChart>
            </ResponsiveContainer>
          )}
          {loading ? <p className="note">Updating…</p> : null}
        </ChartCard>

        <div className="stack sim-outcomes">
          <section className="card">
            <h2 className="card-title">Decision summary</h2>
            <ComparisonTable result={result} saved={saved} savedLabel={savedLabel} />
            {result?.explanation ? <p className="note">{result.explanation}</p> : null}
            <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 12 }}>
              <button type="button" className="btn btn-primary" disabled={overBudget || !productId || loading} onClick={() => void applyReorder()}>
                Create draft reorder
              </button>
              <label className="field" style={{ marginBottom: 0 }}>
                Scenario name
                <input className="input" value={scenarioName} onChange={(e) => setScenarioName(e.target.value)} placeholder="e.g. Faster replenishment" />
              </label>
              <button type="button" className="btn btn-secondary" disabled={saving || !productId} onClick={() => void saveScenario()}>
                {saving ? "Saving…" : "Save scenario"}
              </button>
            </div>
          </section>
          <section className="card">
            <h2 className="card-title">Saved scenarios</h2>
            {scenarios.length === 0 ? (
              <p className="note">None yet. Save the current controls to reopen them later.</p>
            ) : (
              <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
                {scenarios.slice(0, 8).map((s) => (
                  <li key={s.id} style={{ display: "flex", justifyContent: "space-between", gap: 8, alignItems: "center", padding: "8px 0", borderBottom: "1px solid var(--color-border)" }}>
                    <span>
                      <strong>{s.name || `Scenario ${s.id}`}</strong>
                      <div className="note" style={{ margin: 0 }}>{formatDateTime(s.created_at)}</div>
                    </span>
                    <button type="button" className="btn btn-secondary btn-sm" onClick={() => void reopen(s.id)}>
                      Reopen
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </div>
    </>
  );
}

function mergeSeries(result: SimulateResponse | null) {
  if (!result) return [];
  const map = new Map<string, { date: string; baseline?: number; proposed?: number }>();
  for (const p of result.baseline_series) map.set(p.date, { date: p.date, baseline: p.inventory });
  for (const p of result.proposed_series) {
    const cur = map.get(p.date) ?? { date: p.date };
    cur.proposed = p.inventory;
    map.set(p.date, cur);
  }
  return [...map.values()].sort((a, b) => a.date.localeCompare(b.date));
}

function ComparisonTable({
  result,
  saved,
  savedLabel,
}: {
  result: SimulateResponse | null;
  saved: SimulateResponse | null;
  savedLabel: string | null;
}) {
  const rows = [
    row("Unmet demand", result?.baseline_metrics.unmet_demand_units, result?.proposed_metrics.unmet_demand_units, saved?.proposed_metrics.unmet_demand_units, false),
    row("Stockout days", result?.baseline_metrics.stockout_days, result?.proposed_metrics.stockout_days, saved?.proposed_metrics.stockout_days, false),
    row("Revenue", result?.baseline_metrics.revenue_paise, result?.proposed_metrics.revenue_paise, saved?.proposed_metrics.revenue_paise, true),
    row("Gross margin proxy", result?.baseline_metrics.gross_margin_paise, result?.proposed_metrics.gross_margin_paise, saved?.proposed_metrics.gross_margin_paise, true),
    row("Purchase cost", result?.baseline_metrics.purchase_cost_paise, result?.proposed_metrics.purchase_cost_paise, saved?.proposed_metrics.purchase_cost_paise, true),
  ];
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>Metric</th>
            <th>Current</th>
            <th>Proposed</th>
            {saved ? <th>{savedLabel ?? "Saved"}</th> : null}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.metric}>
              <td>{r.metric}</td>
              <td className="tabular">{r.base}</td>
              <td className="tabular">{r.proposed}</td>
              {saved ? <td className="tabular">{r.saved}</td> : null}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function row(metric: string, base: number | null | undefined, proposed: number | null | undefined, saved: number | null | undefined, money: boolean) {
  const fmt = (v: number | null | undefined) => (v == null || Number.isNaN(v) ? "N/A" : money ? formatPaise(v) : formatNumber(v));
  return { metric, base: fmt(base), proposed: fmt(proposed), saved: fmt(saved) };
}

function deltaText(base?: number | null, proposed?: number | null, money = false) {
  if (base == null || proposed == null) return "Versus current plan once both values exist";
  const diff = proposed - base;
  const rendered = money ? formatPaise(Math.abs(diff)) : formatNumber(Math.abs(diff));
  if (diff === 0) return "Same as the current plan";
  return `${diff > 0 ? "Higher" : "Lower"} by ${rendered} vs current plan`;
}

function probDelta(base?: number | null, proposed?: number | null) {
  if (base == null || proposed == null) return "Model probability · simulated supply";
  const pp = (proposed - base) * 100;
  return `${pp > 0 ? "+" : ""}${pp.toFixed(1)} pp vs current plan`;
}

function fmtProb(v: number | null | undefined) {
  if (v == null || Number.isNaN(v)) return "N/A";
  return `${(v * 100).toFixed(1)}%`;
}

function defaultOrderQty(product: ProductRow | null | undefined): number {
  if (!product) return 12;
  const pack = Math.max(1, product.pack_size ?? 12);
  const point = product.reorder_point ?? pack;
  return Math.max(pack, Math.ceil(point / pack) * pack);
}