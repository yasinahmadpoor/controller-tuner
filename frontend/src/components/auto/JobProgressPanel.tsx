import { useEffect } from "react";

import { useCancelJob, useJob } from "../../hooks/queries";
import { useJobEvents } from "../../hooks/useJobEvents";
import { formatNumber } from "../../lib/format";
import type { OptimizeResult } from "../../types/api";
import { ErrorBanner } from "../common/ErrorBanner";
import { LoadingSpinner } from "../common/LoadingSpinner";

function asNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function JobProgressPanel({
  jobId,
  onSucceeded,
  onReset,
}: {
  jobId: string;
  onSucceeded: (result: OptimizeResult) => void;
  onReset: () => void;
}) {
  const job = useJob(jobId);
  const terminal =
    job.data?.status === "succeeded" ||
    job.data?.status === "failed" ||
    job.data?.status === "cancelled";
  const events = useJobEvents(jobId, !terminal);
  const cancel = useCancelJob(jobId);
  const progress = events.progress ?? job.data?.progress ?? {};
  const status = job.data?.status ?? "queued";

  useEffect(() => {
    if (job.data?.status === "succeeded" && job.data.result) {
      onSucceeded(job.data.result);
    }
  }, [job.data?.result, job.data?.status, onSucceeded]);

  if (job.isError) {
    return (
      <ErrorBanner
        title="Could not load job"
        message={job.error instanceof Error ? job.error.message : "Job polling failed"}
        onDismiss={onReset}
      />
    );
  }

  return (
    <section className="card p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-bold text-slate-900">Background optimization</h2>
            <span
              className={[
                "rounded-full px-2.5 py-1 text-xs font-semibold capitalize",
                status === "succeeded"
                  ? "bg-emerald-50 text-emerald-700"
                  : status === "failed"
                    ? "bg-rose-50 text-rose-700"
                    : status === "cancelled"
                      ? "bg-amber-50 text-amber-800"
                      : "bg-accent-50 text-accent-700",
              ].join(" ")}
            >
              {status}
            </span>
          </div>
          <p className="mt-1 font-mono text-xs text-slate-500">job_id {jobId}</p>
        </div>
        <div className="flex gap-2">
          {status === "queued" || status === "running" ? (
            <button
              type="button"
              onClick={() => cancel.mutate()}
              disabled={cancel.isPending}
              className="rounded-xl border border-rose-200 px-3 py-2 text-xs font-semibold text-rose-700 hover:bg-rose-50 disabled:opacity-50"
            >
              {cancel.isPending ? "Cancelling…" : "Cancel job"}
            </button>
          ) : (
            <button type="button" onClick={onReset} className="btn-secondary">
              Start another run
            </button>
          )}
        </div>
      </div>

      {job.isPending ? (
        <div className="mt-4">
          <LoadingSpinner label="Waiting for the worker" />
        </div>
      ) : null}

      {events.fallback && status !== "succeeded" ? (
        <p className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-900">
          Live progress stream unavailable; falling back to polling.
        </p>
      ) : null}

      {status === "failed" ? (
        <div className="mt-4">
          <ErrorBanner
            title="Optimization failed"
            message={job.data?.error?.message ?? "The worker reported a failure."}
            onDismiss={onReset}
          />
        </div>
      ) : null}
      {status === "cancelled" ? (
        <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          The optimization was cancelled. Partial progress is not saved as a result.
        </div>
      ) : null}

      <dl className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {[
          ["Generation", asNumber(progress.generation)],
          ["NFE", asNumber(progress.cumulative_nfe)],
          ["Wall time", asNumber(progress.cumulative_wall_time)],
          ["Best score", asNumber(progress.best_score_so_far)],
          ["Kp", asNumber(progress.Kp)],
          ["Ki", asNumber(progress.Ki)],
          ["Kd", asNumber(progress.Kd)],
        ].map(([label, value]) => (
          <div key={String(label)} className="rounded-xl bg-slate-50 px-3 py-3">
            <dt className="label">{label}</dt>
            <dd className="mt-1 font-mono text-lg font-semibold text-slate-900">
              {value === null ? "—" : formatNumber(value as number)}
            </dd>
          </div>
        ))}
      </dl>

      {status === "running" || status === "queued" ? (
        <p className="mt-4 text-xs text-slate-500">
          The worker publishes one progress event per generation. Polling is active every
          second until the job reaches a terminal state.
        </p>
      ) : null}
    </section>
  );
}
