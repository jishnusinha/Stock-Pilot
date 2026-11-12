import { useEffect, useState } from "react";
import { Outlet, useNavigate } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";

const COMPACT_KEY = "stockpilot-sidebar-compact";

export function AppShell() {
  const [mobileNav, setMobileNav] = useState(false);
  const [compact, setCompact] = useState(() => localStorage.getItem(COMPACT_KEY) === "1");
  const [search, setSearch] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    localStorage.setItem(COMPACT_KEY, compact ? "1" : "0");
  }, [compact]);

  function onSearchChange(v: string) {
    setSearch(v);
    if (v.trim().length >= 2) {
      navigate(`/inventory?search=${encodeURIComponent(v.trim())}`);
    }
  }

  return (
    <div className="app-shell">
      {mobileNav ? (
        <button type="button" className="nav-backdrop" aria-label="Close menu" onClick={() => setMobileNav(false)} />
      ) : null}
      <Sidebar
        mobileOpen={mobileNav}
        compact={compact}
        onNavigate={() => setMobileNav(false)}
        onToggleCompact={() => setCompact((c) => !c)}
      />
      <div className="app-main">
        <Topbar
          onMenuClick={() => setMobileNav((o) => !o)}
          searchValue={search}
          onSearchChange={onSearchChange}
        />
        <main className="app-content" id="main-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
