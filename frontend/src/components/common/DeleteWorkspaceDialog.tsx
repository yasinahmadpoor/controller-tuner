import { useDeleteSystem } from "../../hooks/queries";
import { getErrorMessage } from "../../lib/errors";
import { formatDate } from "../../lib/format";
import type { SystemSummary } from "../../types/api";
import { ErrorBanner } from "./ErrorBanner";
import { useToast } from "./ToastHost";

export function DeleteWorkspaceDialog({
  workspace,
  onClose,
  onDeleted,
}: {
  workspace: SystemSummary;
  onClose: () => void;
  onDeleted: (workspace: SystemSummary) => void;
}) {
  const remove = useDeleteSystem();
  const { pushToast } = useToast();

  async function confirmDelete() {
    try {
      await remove.mutateAsync(workspace.system_id);
      pushToast(`Deleted ${workspace.name}`, "success");
      onDeleted(workspace);
    } catch {
      // Rendered by the error banner below.
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/40 p-4 backdrop-blur-sm">
      <div
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="delete-workspace-title"
        className="card my-12 w-full max-w-lg p-6"
      >
        <h2 id="delete-workspace-title" className="text-xl font-bold text-slate-900">
          Delete workspace?
        </h2>
        <p className="mt-2 text-sm text-slate-600">
          <strong>{workspace.name}</strong>
        </p>
        <p className="mt-1 font-mono text-xs text-slate-500">
          {workspace.system_id} · created {formatDate(workspace.created_at)}
        </p>

        <div className="mt-4 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-900">
          This permanently deletes the workspace, all simulation and optimization
          history, and any queued jobs. Artifact blobs are removed when unreferenced.
          This cannot be undone.
        </div>

        {remove.isError ? (
          <div className="mt-4">
            <ErrorBanner
              title="Could not delete workspace"
              message={getErrorMessage(remove.error)}
              onDismiss={() => remove.reset()}
            />
          </div>
        ) : null}

        <div className="mt-6 flex flex-wrap justify-end gap-3">
          <button type="button" onClick={onClose} className="btn-secondary">
            Cancel
          </button>
          <button
            type="button"
            onClick={() => void confirmDelete()}
            disabled={remove.isPending}
            className="inline-flex items-center justify-center rounded-xl bg-rose-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-rose-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {remove.isPending ? "Deleting…" : "Delete workspace permanently"}
          </button>
        </div>
      </div>
    </div>
  );
}
