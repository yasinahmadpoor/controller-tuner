import { formatDate } from "../../lib/format";
import type { CatalogEntry, SystemSummary } from "../../types/api";

export function WorkspacePickerDialog({
  entry,
  workspaces,
  busy,
  onOpen,
  onCreate,
  onClose,
}: {
  entry: CatalogEntry;
  workspaces: SystemSummary[];
  busy: boolean;
  onOpen: (workspace: SystemSummary) => void;
  onCreate: () => void;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-40 flex items-start justify-center overflow-y-auto bg-slate-900/40 p-4 backdrop-blur-sm">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="workspace-picker-title"
        className="card my-10 w-full max-w-2xl p-6"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 id="workspace-picker-title" className="text-xl font-bold text-slate-900">
              Choose a {entry.name} workspace
            </h2>
            <p className="mt-1 text-sm text-slate-500">
              History belongs to a workspace. Pick the one whose runs you want to continue.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close workspace picker"
            className="rounded-lg px-2 py-1 text-xl text-slate-500 hover:bg-slate-100"
          >
            ×
          </button>
        </div>

        <ul className="mt-5 divide-y divide-slate-100 rounded-xl border border-slate-200">
          {workspaces.map((workspace) => (
            <li
              key={workspace.system_id}
              className="flex flex-wrap items-center justify-between gap-3 px-4 py-3"
            >
              <div>
                <p className="text-sm font-semibold text-slate-900">
                  Created {formatDate(workspace.created_at)}
                </p>
                <p className="mt-0.5 font-mono text-xs text-slate-500">
                  {workspace.system_id}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => onOpen(workspace)}
                  className="btn-secondary"
                >
                  Open workspace
                </button>
              </div>
            </li>
          ))}
        </ul>

        <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
          <p className="text-xs text-slate-500">
            Creating a new workspace starts with empty history.
          </p>
          <button
            type="button"
            onClick={onCreate}
            disabled={busy}
            className="btn-primary"
          >
            {busy ? "Creating…" : "Create new workspace"}
          </button>
        </div>
      </div>
    </div>
  );
}
