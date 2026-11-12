import { useEffect, useRef, useState } from "react";
import { Bell, Menu, Search, Settings } from "lucide-react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { DashboardAlert } from "../types/api";
import { ProvenancePill } from "./ProvenancePill";

const CRUMBS: Record<string, string> = {
  "/": "Command Center",
  "/inventory": "Inventory Explorer",
  "/simulator": "What-If Simulator",
  "/agents": "Agent Intelligence",
  "/performance": "Model Performance",
  "/reorders": "Reorders",
  "/settings": "Settings",
};

export function Topbar({
  onMenuClick,
  searchValue,
  onSearchChange,
}: {
  onMenuClick?: () => void;
  searchValue?: string;
  onSearchChange?: (v: string) => void;
}) {
  const location = useLocation();
  const navigate = useNavigate();
  const searchRef = useRef<HTMLInputElement>(null);
  const [alerts, setAlerts] = useState<DashboardAlert[] | null>(null);
  const [alertError, setAlertError] = useState<string | null>(null);
  const [notesOpen, setNotesOpen] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api
      .dashboard()
      .then((d) => {
        if (!cancelled) {
          setAlerts(d.alerts ?? []);
          setAlertError(null);
        }
      })
      .catch((e: Error) => {
        if (!cancelled) setAlertError(e.message || "Alerts unavailable");
      });
    return () => {
      cancelled = true;
    };
  }, [location.pathname]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        searchRef.current?.focus();
      }
      if (e.key === "Escape") {
        setNotesOpen(false);
        setAccountOpen(false);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const crumb = CRUMBS[location.pathname] ?? "StockPilot";
  const count = alerts?.length ?? 0;

  return (
    <header className="app-topbar">
      {onMenuClick ? (
        <button type="button" className="icon-btn" aria-label="Open menu" onClick={onMenuClick} id="mobile-menu-btn">
          <Menu size={18} />
        </button>
      ) : null}
      <div className="crumb hide-sm">
        StockPilot / <strong>{crumb}</strong>
      </div>
      <div className="search-wrap">
        <Search size={16} />
        <input
          ref={searchRef}
          type="search"
          className="input"
          placeholder="Search products, SKUs, or suppliers"
          aria-label="Search products"
          value={searchValue ?? ""}
          onChange={(e) => onSearchChange?.(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              const q = (searchValue ?? "").trim();
              navigate(q ? `/inventory?search=${encodeURIComponent(q)}` : "/inventory");
            }
          }}
        />
        <span className="kbd hide-sm">Ctrl K</span>
      </div>
      <div className="hide-sm">
        <ProvenancePill />
      </div>
      <div className="menu-anchor">
        <button
          type="button"
          className="icon-btn"
          aria-label={count ? `Notifications, ${count} inventory alerts` : "Notifications"}
          aria-expanded={notesOpen}
          onClick={() => {
            setNotesOpen((o) => !o);
            setAccountOpen(false);
          }}
        >
          <Bell size={18} />
          {count > 0 ? <span className="count-pip">{count}</span> : null}
        </button>
        {notesOpen ? (
          <div className="popover" role="dialog" aria-label="Inventory alerts">
            <div style={{ padding: "6px 8px 8px", fontWeight: 650 }}>Inventory alerts</div>
            {alertError ? <p className="note">{alertError}</p> : null}
            {!alertError && alerts && alerts.length === 0 ? (
              <p className="note">No inventory alerts from the latest dashboard response.</p>
            ) : null}
            {alerts?.map((alert) => (
              <button
                key={alert.id}
                type="button"
                className="popover-item"
                onClick={() => {
                  setNotesOpen(false);
                  if (alert.product_id) navigate(`/inventory?product=${alert.product_id}`);
                }}
              >
                <strong>{alert.title}</strong>
                <div className="note" style={{ margin: 0 }}>
                  {alert.message}
                </div>
              </button>
            ))}
          </div>
        ) : null}
      </div>
      <div className="menu-anchor">
        <button
          type="button"
          className="identity-chip"
          aria-expanded={accountOpen}
          aria-label="Demo account menu"
          onClick={() => {
            setAccountOpen((o) => !o);
            setNotesOpen(false);
          }}
        >
          <span className="avatar">SR</span>
          <span className="hide-sm">Summit Retail Co.</span>
        </button>
        {accountOpen ? (
          <div className="popover" role="menu" style={{ width: 240 }}>
            <div style={{ padding: 10 }}>
              <strong>Summit Retail Co.</strong>
              <div className="note" style={{ margin: "4px 0 0" }}>
                Demo identity · single retailer
              </div>
            </div>
            <Link to="/settings" className="popover-item" onClick={() => setAccountOpen(false)} role="menuitem">
              <Settings size={14} style={{ marginRight: 6 }} /> Settings
            </Link>
          </div>
        ) : null}
      </div>
    </header>
  );
}
