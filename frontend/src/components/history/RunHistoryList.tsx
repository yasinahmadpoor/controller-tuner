import { useState } from "react";
import { Link } from "react-router-dom";

import { formatDate, formatMetric } from "../../lib/format";
import type { RunSummary } from "../../types/api";
import { EmptyState } from "../common/EmptyState";
import { Pagination } from "../common/Pagination";

interface RunHistoryListProps {
  items: RunSummary[];
  total: number;
  limit: number;
  offset: number;
  onOffsetChange: (offset: number) => void;
  onReopen?: (run: RunSummary) => void;
  onDelete: (run: RunSummary) => void;
  deletingId?: string | null;
}

function summaryMetrics(run: RunSummary): Array<[string, string]> {
  const summary = run.summary ?? {};
  const preferred =
    run.run_type === "optimization"
      ? ["mse", "settling_time", "overshoot"]
      : ["mse", "settling_time", "stable"];
  return preferred
    .filter((key) => key in summary)
    .map((key) => [key, formatMetric(summary[key])]);
}

export function RunHistoryList({
  items,
  total,
  limit,
  offset,
  onOffsetChange,
  onReopen,
  onDelete,
  deletingId,
}: RunHistoryListProps) {
  const [confirmingId, setConfirmingId] = useState<string | null>(null);

  if (items.length === 0) {
    return (
      <EmptyState title="No runs in this workspace">
        Run a simulation or optimization to build history here. History is scoped to
        the current workspace; older runs may belong to a different workspace, and
        optimization runs are listed under the Optimizations toggle.
      </EmptyState>
    );
  }

  return (
    <div className="space-y-4">
      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
        <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3 font-semibold">When</th>
              <th className="px-4 py-3 font-semibold">Type</th>
              <th className="px-4 py-3 font-semibold">Status</th>
              <th className="px-4 py-3 font-semibold">Summary</th>
              <th className="px-4 py-3 text-right font-semibold">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {items.map((run) => {
              const destination = `/runs/${run.run_id}?type=${run.run_type}`;
              return (
                <tr key={run.run_id} className="align-middle">
                  <td className="whitespace-nowrap px-4 py-3 text-slate-700">
                    {formatDate(run.created_at)}
                  </td>
                  <td className="px-4 py-3">
                    <span className="font-semibold text-slate-900">
                      {run.run_type === "simulation"
                        ? (run.controller_type ?? "Simulation")
                        : "GA optimization"}
                    </span>
                    <span className="mt-0.5 block text-xs text-slate-400">
                      {run.engine}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={[
                        "inline-flex rounded-full px-2.5 py-1 text-xs font-semibold",
                        run.status === "succeeded"
                          ? "bg-emerald-50 text-emerald-700"
                          : "bg-rose-50 text-rose-700",
                      ].join(" ")}
                    >
                      {run.status}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-slate-600">
                      {summaryMetrics(run).map(([key, value]) => (
                        <span key={key}>
                          <span className="text-slate-400">{key}:</span> {value}
                        </span>
                      ))}
                      {run.best_params
                        ? Object.entries(run.best_params).map(([name, value]) => (
                            <span key={`gain-${name}`}>
                              <span className="text-slate-400">{name}:</span>{" "}
                              {formatMetric(value)}
                            </span>
                          ))
                        : null}
                      {run.stop_reason ? (
                        <span>
                          <span className="text-slate-400">stop:</span> {run.stop_reason}
                        </span>
                      ) : null}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap justify-end gap-2">
                      {onReopen ? (
                        <button
                          type="button"
                          onClick={() => onReopen(run)}
                          className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                        >
                          Reopen
                        </button>
                      ) : (
                        <Link
                          to={destination}
                          className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                        >
                          Reopen
                        </Link>
                      )}
                      {confirmingId === run.run_id ? (
                        <>
                          <button
                            type="button"
                            onClick={() => {
                              onDelete(run);
                              setConfirmingId(null);
                            }}
                            disabled={deletingId === run.run_id}
                            className="rounded-lg bg-rose-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-rose-700 disabled:opacity-50"
                          >
                            {deletingId === run.run_id ? "Deleting…" : "Confirm delete"}
                          </button>
                          <button
                            type="button"
                            onClick={() => setConfirmingId(null)}
                            className="rounded-lg px-2 py-1.5 text-xs font-semibold text-slate-500"
                          >
                            Cancel
                          </button>
                        </>
                      ) : (
                        <button
                          type="button"
                          onClick={() => setConfirmingId(run.run_id)}
                          className="rounded-lg border border-rose-200 px-3 py-1.5 text-xs font-semibold text-rose-700 hover:bg-rose-50"
                        >
                          Delete
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <Pagination total={total} limit={limit} offset={offset} onOffsetChange={onOffsetChange} />
    </div>
  );
}
