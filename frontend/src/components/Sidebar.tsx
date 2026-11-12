import { NavLink } from "react-router-dom";
import {
  BarChart3,
  Boxes,
  Brain,
  LayoutDashboard,
  LineChart,
  Package,
  Settings,
  SlidersHorizontal,
} from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api/client";

const nav = [
  { to: "/", label: "Command Center", icon: LayoutDashboard, end: true },
  { to: "/inventory", label: "Inventory", icon: Boxes },
  { to: "/simulator", label: "What-If Simulator", icon: SlidersHorizontal },
  { to: "/agents", label: "Agent Intelligence", icon: Brain },
  { to: "/performance", label: "Model Performance", icon: LineChart },
  { to: "/reorders", label: "Reorders", icon: Package },
];

type Props = { mobileOpen?: boolean; onNavigate?: () => void };

export function Sidebar({ mobileOpen, onNavigate }: Props) {
  const [models, setModels] = useState<number | null>(null);
  const [dbReady, setDbReady] = useState<boolean | null>(null);

  useEffect(() => {
    api.health().then((h) => {
      setModels(h.models_available);
      setDbReady(h.db_ready);
    }).catch(() => {
      setModels(null);
      setDbReady(null);
    });
  }, []);

  const cls = mobileOpen ? "app-sidebar mobile-open" : "app-sidebar";

  return (
    <aside className={cls} aria-label="Main navigation">
      <p className="brand" style={{ display: "flex", alignItems: "center", gap: 8, fontWeight: 700, fontSize: 18, margin: "0 0 24px" }}>
        <BarChart3 size={22} color="var(--color-primary)" />
        StockPilot
      </p>
      <nav style={{ flex: 1 }}>
        <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 4 }}>
          {nav.map(({ to, label, icon: Icon, end }) => (
            <li key={to}>
              <NavLink
                to={to}
                end={end}
                onClick={onNavigate}
                style={({ isActive }) => ({
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  padding: "10px 12px",
                  borderRadius: 10,
                  color: isActive ? "var(--color-primary)" : "var(--color-text)",
                  background: isActive ? "var(--color-mint)" : "transparent",
                  fontWeight: isActive ? 600 : 400,
                  textDecoration: "none",
                })}
              >
                <Icon size={18} />
                {label}
              </NavLink>
            </li>
          ))}
          <li>
            <NavLink
              to="/settings"
              onClick={onNavigate}
              style={({ isActive }) => ({
                display: "flex",
                alignItems: "center",
                gap: 10,
                padding: "10px 12px",
                borderRadius: 10,
                color: isActive ? "var(--color-primary)" : "var(--color-text-muted)",
                textDecoration: "none",
              })}
            >
              <Settings size={18} />
              Settings
            </NavLink>
          </li>
        </ul>
      </nav>
      <div
        className="demo-panel"
        style={{
          marginTop: "auto",
          padding: 12,
          background: "var(--color-mint)",
          borderRadius: 12,
          border: "1px solid var(--color-border)",
          fontSize: 12,
        }}
      >
        <strong style={{ display: "block", marginBottom: 6 }}>Demo Mode</strong>
        <span style={{ color: "var(--color-text-muted)" }}>Summit Retail Co. · SYNTHETIC_DEMO</span>
        <div style={{ marginTop: 8 }}>
          <span>ML models: </span>
          <strong>
            {models != null ? `${models}/10 fitted` : "—"}
          </strong>
        </div>
        <div>
          Database: <strong>{dbReady == null ? "—" : dbReady ? "Ready" : "Offline"}</strong>
        </div>
      </div>
    </aside>
  );
}
