import { useQuery } from "@tanstack/react-query";
import { NavLink, Outlet } from "react-router-dom";

import { API_BASE } from "../api/client";

async function getBackendHealth(): Promise<{ status: string }> {
  const response = await fetch(`${API_BASE}/health`);
  if (!response.ok) {
    throw new Error("Backend unavailable");
  }
  return (await response.json()) as { status: string };
}

export function AppShell() {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: getBackendHealth,
    retry: 1,
    refetchInterval: 30_000,
  });

  return (
    <div className="min-h-screen bg-canvas">
      <header className="border-b border-slate-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-4 py-4 sm:px-6">
          <NavLink to="/systems" className="flex items-center gap-3">
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-accent-600 text-sm font-black text-white">
              CT
            </span>
            <span>
              <span className="block text-sm font-bold uppercase tracking-widest text-slate-500">
                Controller
              </span>
              <span className="-mt-0.5 block text-lg font-bold text-slate-900">Tuner</span>
            </span>
          </NavLink>
          <div className="flex items-center gap-3 text-xs font-medium text-slate-500">
            <span
              className={[
                "inline-flex items-center gap-2 rounded-full border px-3 py-1.5",
                health.isSuccess
                  ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                  : health.isError
                    ? "border-rose-200 bg-rose-50 text-rose-700"
                    : "border-slate-200 bg-slate-50 text-slate-600",
              ].join(" ")}
            >
              <span
                className={[
                  "h-2 w-2 rounded-full",
                  health.isSuccess
                    ? "bg-emerald-500"
                    : health.isError
                      ? "bg-rose-500"
                      : "bg-slate-400",
                ].join(" ")}
              />
              {health.isSuccess ? "Backend online" : health.isError ? "Backend offline" : "Checking backend"}
            </span>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
        <Outlet />
      </main>
    </div>
  );
}
