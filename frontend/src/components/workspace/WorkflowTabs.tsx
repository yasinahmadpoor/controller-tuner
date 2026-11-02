import { NavLink } from "react-router-dom";

const tabs = [
  { id: "manual", label: "Manual" },
  { id: "auto", label: "Auto-Tune" },
  { id: "history", label: "History" },
] as const;

export function WorkflowTabs({ systemId }: { systemId: string }) {
  return (
    <nav className="flex flex-wrap gap-2" aria-label="Workflow tabs">
      {tabs.map((tab) => {
        return (
          <NavLink
            key={tab.id}
            to={`/systems/${systemId}/${tab.id}`}
            className={({ isActive }) =>
              [
                "inline-flex items-center rounded-xl border px-4 py-2 text-sm font-semibold transition",
                isActive
                  ? "border-accent-600 bg-accent-600 text-white"
                  : "border-slate-300 bg-white text-slate-700 hover:bg-slate-50",
              ].join(" ")
            }
          >
            {tab.label}
          </NavLink>
        );
      })}
    </nav>
  );
}
