import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import {
  BarChart3,
  Boxes,
  Brain,
  LayoutDashboard,
  LineChart,
  Package,
  PanelLeftClose,
  PanelLeftOpen,
  Settings,
  SlidersHorizontal,
} from "lucide-react";
import { api } from "../api/client";

const nav = [
  { to: "/", label: "Command Center", icon: LayoutDashboard, end: true },
  { to: "/inventory", label: "Inventory", icon: Boxes },
  { to: "/simulator", label: "What-If Simulator", icon: SlidersHorizontal },
  { to: "/agents", label: "Agent Intelligence", icon: Brain },
  { to: "/performance", label: "Model Performance", icon: LineChart },
  { to: "/reorders", label: "Reorders", icon: Package },
  { to: "/settings", label: "Settings", icon: Settings },
];

type Props = {
  mobileOpen?: boolean;
  compact?: boolean;
  onNavigate?: () => void;
  onToggleCompact?: () => void;
};

export function Sidebar({ mobileOpen, compact, onNavigate, onToggleCompact }: Props) {
  const [models, setModels] = useState<number | null>(null);
  const [expected, setExpected] = useState(10);
  const [dbReady, setDbReady] = useState<boolean | null>(null);

  useEffect(() => {
    api
      .health()
      .then((h) => {
        setModels(h.models_available);
        setExpected(h.models_expected || 10);
        setDbReady(h.db_ready);
      })
      .catch(() => {
        setModels(null);
        setDbReady(false);
      });
  }, []);

  const cls = ["app-sidebar", mobileOpen ? "mobile-open" : "", compact ? "compact" : ""].filter(Boolean).join(" ");

  return (
    <aside className={cls} aria-label="Main navigation">
      <div className="brand">
        <span className="brand-mark" aria-hidden>
          <BarChart3 size={18} />
        </span>
        <span className="brand-word">StockPilot</span>
      </div>
      <nav style={{ flex: 1 }}>
        <ul className="nav-list">
          {nav.map(({ to, label, icon: Icon, end }) => (
            <li key={to}>
              <NavLink
                to={to}
                end={end}
                onClick={onNavigate}
                title={label}
                className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}
              >
                <Icon size={18} />
                <span className="nav-label">{label}</span>
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
      <div className="sidebar-foot">
        <button type="button" className="btn btn-ghost btn-sm" onClick={onToggleCompact} aria-pressed={compact}>
          {compact ? <PanelLeftOpen size={16} /> : <PanelLeftClose size={16} />}
          <span className="compact-label">{compact ? "Expand" : "Compact"}</span>
        </button>
        <div className="demo-panel">
          <strong>Summit Retail Co.</strong>
          <div style={{ marginTop: 6 }}>Demo retailer · SYNTHETIC_DEMO</div>
          <div style={{ marginTop: 8 }}>
            <span className={`status-dot ${models != null && models > 0 ? "ok" : "bad"}`} />
            ML models: <strong>{models != null ? `${models}/${expected} fitted` : "unreachable"}</strong>
          </div>
          <div>
            <span className={`status-dot ${dbReady ? "ok" : dbReady === false ? "bad" : ""}`} />
            Database: <strong>{dbReady == null ? "—" : dbReady ? "Connected" : "Offline"}</strong>
          </div>
        </div>
      </div>
    </aside>
  );
}
