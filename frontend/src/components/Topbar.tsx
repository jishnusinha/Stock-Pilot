import { Bell, Menu, Search } from "lucide-react";
import { ProvenancePill } from "./ProvenancePill";

export function Topbar({
  onMenuClick,
  searchValue,
  onSearchChange,
}: {
  onMenuClick?: () => void;
  searchValue?: string;
  onSearchChange?: (v: string) => void;
}) {
  return (
    <header className="app-topbar">
      {onMenuClick ? (
        <button
          type="button"
          className="btn btn-secondary"
          aria-label="Open menu"
          onClick={onMenuClick}
          style={{ padding: "8px", display: "none" }}
          id="mobile-menu-btn"
        >
          <Menu size={20} />
        </button>
      ) : null}
      <div style={{ flex: 1, maxWidth: 480, position: "relative" }}>
        <Search
          size={18}
          style={{
            position: "absolute",
            left: 12,
            top: "50%",
            transform: "translateY(-50%)",
            color: "var(--color-text-muted)",
          }}
        />
        <input
          type="search"
          className="input"
          placeholder="Search SKU, product, supplier…"
          aria-label="Search"
          value={searchValue ?? ""}
          onChange={(e) => onSearchChange?.(e.target.value)}
          style={{ paddingLeft: 40 }}
        />
      </div>
      <ProvenancePill />
      <button type="button" className="btn btn-secondary" aria-label="Notifications" style={{ padding: 8 }}>
        <Bell size={20} />
      </button>
      <div
        aria-label="Demo user"
        style={{
          width: 36,
          height: 36,
          borderRadius: "50%",
          background: "var(--color-primary)",
          color: "#fff",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontWeight: 600,
          fontSize: 13,
        }}
      >
        SR
      </div>
    </header>
  );
}
