import { Link, useParams, useSearchParams } from "react-router-dom";

import { useRun } from "../../hooks/queries";
import { formatDate, formatMetric, formatNumber, metricLabel } from "../../lib/format";
import type {
  OptimizationRunDetail,
  RunType,
  SimulationRunDetail,
} from "../../types/api";
import { ErrorBanner } from "../common/ErrorBanner";
import { LoadingSpinner } from "../common/LoadingSpinner";
import { StabilityBadge } from "../common/StabilityBadge";
import { ControlChart } from "../results/ControlChart";
import { MetricsPanel } from "../results/MetricsPanel";
import { TrajectoryChart } from "../results/TrajectoryChart";
import { getErrorMessage } from "../../lib/errors";
import { readRunTrajectory } from "../../lib/runCache";

function asNumber(value: unknown, fallback = 0): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function SimulationDetail({ detail }: { detail: SimulationRunDetail }) {
  const target = asNumber(detail.overrides?.target, 0);
  const trajectory = detail.trajectory ?? readRunTrajectory(detail.run_id);
  return (
    <div className="space-y-4">
      <section className="card p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-bold text-slate-900">
              {detail.controller_type} simulation
            </h1>
            <p className="mt-1 text-xs text-slate-500">
              run_id <span className="font-mono text-slate-700">{detail.run_id}</span> ·{" "}
              {formatDate(detail.created_at)}
            </p>
          </div>
          <StabilityBadge stable={detail.metrics.stable} />
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          {Object.entries(detail.params).map(([name, value]) => (
            <span
              key={name}
              className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700"
            >
              {name} = {formatNumber(value)}
            </span>
          ))}
        </div>
      </section>

      {trajectory ? (
        <>
          <TrajectoryChart
            timePoints={trajectory.time_points}
            trajectory={trajectory.trajectory}
            target={target}
          />
          <ControlChart
            timePoints={trajectory.time_points}
            controlSignals={trajectory.control_signals}
          />
        </>
      ) : (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          This run was saved without trajectory arrays, so only its metrics can be restored.
          Enable <code className="font-mono">PERSIST_TRAJECTORIES</code> to retain charts.
        </div>
      )}
      <MetricsPanel
        metrics={detail.metrics}
        nonFiniteMetrics={detail.non_finite_metrics}
      />
    </div>
  );
}

function OptimizationDetail({ detail }: { detail: OptimizationRunDetail }) {
  return (
    <div className="space-y-4">
      <section className="card p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-bold text-slate-900">GA optimization</h1>
            <p className="mt-1 text-xs text-slate-500">
              run_id <span className="font-mono text-slate-700">{detail.run_id}</span> ·{" "}
              {formatDate(detail.created_at)}
            </p>
          </div>
          <span className="rounded-full bg-accent-50 px-3 py-1 text-xs font-semibold text-accent-700">
            {detail.stop_reason ?? detail.status}
          </span>
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          {Object.entries(detail.best_params).map(([name, value]) => (
            <div key={name} className="rounded-xl bg-slate-50 px-3 py-3">
              <p className="label">{name}</p>
              <p className="mt-1 font-mono text-lg font-bold text-slate-900">
                {formatNumber(value, 4)}
              </p>
            </div>
          ))}
        </div>
      </section>

      <section className="card p-5">
        <h2 className="text-base font-bold text-slate-900">Achieved metrics</h2>
        <dl className="mt-3 grid gap-3 sm:grid-cols-2">
          {Object.entries(detail.achieved_metrics)
            .filter(([, value]) => typeof value === "number" || value === null)
            .map(([key, value]) => (
              <div key={key} className="flex justify-between rounded-xl bg-slate-50 px-3 py-2 text-sm">
                <dt className="text-slate-600">{metricLabel(key)}</dt>
                <dd className="font-mono font-semibold text-slate-900">
                  {formatMetric(value as number | null)}
                </dd>
              </div>
            ))}
        </dl>
        <p className="mt-4 text-sm text-slate-600">
          Evaluations: <strong>{detail.num_evaluations ?? "—"}</strong> · GA cost:{" "}
          <strong>{formatMetric(detail.ga_cost)}</strong> · Baseline cost:{" "}
          <strong>{formatMetric(detail.baseline_cost)}</strong>
        </p>
      </section>
    </div>
  );
}

export function RunDetailPage() {
  const { runId } = useParams<{ runId: string }>();
  const [params] = useSearchParams();
  const type = (params.get("type") ?? "simulation") as RunType;
  const run = useRun(runId, type);

  return (
    <div className="space-y-5">
      <Link to="/systems" className="text-sm font-semibold text-accent-700 hover:underline">
        ← Back to systems
      </Link>
      {run.isPending ? (
        <div className="flex justify-center py-20">
          <LoadingSpinner label="Loading run" />
        </div>
      ) : null}
      {run.isError ? (
        <ErrorBanner
          title="Could not load run"
          message={getErrorMessage(run.error)}
          onDismiss={() => void run.refetch()}
        />
      ) : null}
      {run.isSuccess && run.data.run_type === "simulation" ? (
        <SimulationDetail detail={run.data} />
      ) : null}
      {run.isSuccess && run.data.run_type === "optimization" ? (
        <OptimizationDetail detail={run.data} />
      ) : null}
    </div>
  );
}
