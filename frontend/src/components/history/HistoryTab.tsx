import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useDeleteRun, useSystemRuns } from "../../hooks/queries";
import { getErrorMessage } from "../../lib/errors";
import type { RunSummary, RunType } from "../../types/api";
import { ErrorBanner } from "../common/ErrorBanner";
import { LoadingSpinner } from "../common/LoadingSpinner";
import { useToast } from "../common/ToastHost";
import { RunHistoryList } from "./RunHistoryList";

const PAGE_SIZE = 10;

export function HistoryTab({ systemId }: { systemId: string }) {
  const [type, setType] = useState<RunType>("simulation");
  const [offset, setOffset] = useState(0);
  const runs = useSystemRuns(systemId, type, PAGE_SIZE, offset);
  const remove = useDeleteRun(systemId);
  const navigate = useNavigate();
  const { pushToast } = useToast();

  function changeType(next: RunType) {
    setType(next);
    setOffset(0);
  }

  function reopen(run: RunSummary) {
    navigate(`/runs/${run.run_id}?type=${run.run_type}`);
  }

  async function deleteRun(run: RunSummary) {
    try {
      await remove.mutateAsync({ runId: run.run_id, type: run.run_type });
      pushToast("Run deleted", "success");
    } catch {
      // Rendered by the error banner below.
    }
  }

  return (
    <section className="card p-5 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-slate-900">Run history</h2>
          <p className="mt-1 text-sm text-slate-500">
            Reopen a persisted run or remove it permanently.
          </p>
        </div>
        <div className="inline-flex rounded-xl border border-slate-200 bg-slate-50 p-1">
          {(
            [
              ["simulation", "Simulations"],
              ["optimization", "Optimizations"],
            ] as const
          ).map(([value, label]) => (
            <button
              key={value}
              type="button"
              onClick={() => changeType(value)}
              className={[
                "rounded-lg px-3 py-1.5 text-xs font-semibold transition",
                type === value
                  ? "bg-white text-slate-900 shadow-sm"
                  : "text-slate-500 hover:text-slate-700",
              ].join(" ")}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {remove.isError ? (
        <div className="mt-4">
          <ErrorBanner
            title="Could not delete run"
            message={getErrorMessage(remove.error)}
            onDismiss={() => remove.reset()}
          />
        </div>
      ) : null}

      <div className="mt-5">
        {runs.isPending ? (
          <div className="flex justify-center py-10">
            <LoadingSpinner label="Loading history" />
          </div>
        ) : null}
        {runs.isError ? (
          <ErrorBanner
            title="Could not load history"
            message={getErrorMessage(runs.error)}
            onDismiss={() => void runs.refetch()}
          />
        ) : null}
        {runs.isSuccess ? (
          <RunHistoryList
            items={runs.data.items}
            total={runs.data.total}
            limit={runs.data.limit}
            offset={runs.data.offset}
            onOffsetChange={setOffset}
            onReopen={reopen}
            onDelete={(run) => void deleteRun(run)}
            deletingId={remove.isPending ? remove.variables?.runId ?? null : null}
          />
        ) : null}
      </div>
    </section>
  );
}
