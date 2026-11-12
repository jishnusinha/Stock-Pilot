import { lazy, Suspense } from "react";
import { Navigate, Route, Routes, useParams } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { SkeletonCard } from "./components/Skeleton";
import { CommandCenter } from "./pages/CommandCenter";
import { Inventory } from "./pages/Inventory";
import { Simulator } from "./pages/Simulator";
import { Agents } from "./pages/Agents";
import { Performance } from "./pages/Performance";
import { Reorders } from "./pages/Reorders";
import { Settings } from "./pages/Settings";

const InventoryAnalytics = lazy(() =>
  import("./pages/InventoryAnalytics").then((mod) => ({ default: mod.InventoryAnalytics })),
);

export function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<CommandCenter />} />
        <Route
          path="analytics"
          element={
            <Suspense fallback={<SkeletonCard />}>
              <InventoryAnalytics />
            </Suspense>
          }
        />
        <Route path="inventory" element={<Inventory />} />
        <Route path="simulator" element={<Simulator />} />
        <Route path="agents" element={<Agents />} />
        <Route path="performance" element={<Performance />} />
        <Route path="reorders" element={<Reorders />} />
        <Route path="settings" element={<Settings />} />
        <Route path="products" element={<Navigate to="/inventory" replace />} />
        <Route path="products/:id" element={<ProductRedirect />} />
        <Route path="forecast" element={<Navigate to="/" replace />} />
        <Route path="reports" element={<Navigate to="/performance" replace />} />
        <Route
          path="suppliers"
          element={<Navigate to="/inventory?focus=supplier" replace />}
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

function ProductRedirect() {
  const { id } = useParams();
  return <Navigate to={`/inventory?product=${id ?? ""}`} replace />;
}
