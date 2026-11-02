import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { CatalogPage } from "./components/catalog/CatalogPage";
import { RunDetailPage } from "./components/runs/RunDetailPage";
import { WorkspacePage } from "./components/workspace/WorkspacePage";

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Navigate to="/systems" replace />} />
        <Route path="/systems" element={<CatalogPage />} />
        <Route path="/systems/:systemId" element={<WorkspacePage />} />
        <Route path="/systems/:systemId/:tab" element={<WorkspacePage />} />
        <Route path="/runs/:runId" element={<RunDetailPage />} />
        <Route
          path="*"
          element={
            <div className="mx-auto max-w-3xl px-4 py-16 text-center">
              <h1 className="text-2xl font-bold text-slate-900">Page not found</h1>
            </div>
          }
        />
      </Route>
    </Routes>
  );
}
