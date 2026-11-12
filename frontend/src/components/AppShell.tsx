import { useState } from "react";
import { Outlet, useNavigate } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";

export function AppShell() {
  const [mobileNav, setMobileNav] = useState(false);
  const [search, setSearch] = useState("");
  const navigate = useNavigate();

  function onSearchChange(v: string) {
    setSearch(v);
    if (v.trim().length >= 2) {
      navigate(`/inventory?search=${encodeURIComponent(v.trim())}`);
    }
  }

  return (
    <div className="app-shell">
      <Sidebar mobileOpen={mobileNav} onNavigate={() => setMobileNav(false)} />
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
      <style>{`
        @media (max-width: 768px) {
          #mobile-menu-btn { display: inline-flex !important; }
        }
      `}</style>
    </div>
  );
}
