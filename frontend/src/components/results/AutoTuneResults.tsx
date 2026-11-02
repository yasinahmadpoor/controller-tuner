import { exportGainsCsv, exportGainsJson } from "../../lib/export";
import { formatNumber } from "../../lib/format";
import type { MetricName, OptimizeResult } from "../../types/api";
import { MetricsVsTargetsTable } from "./MetricsVsTargetsTable";
import { ProgressCharts } from "./ProgressCharts";
import { StopReasonBadge } from "./StopReasonBadge";

export function AutoTuneResults({
  result,
  targets,
}: {
  result: OptimizeResult;
  targets: Partial<Record<MetricName, number>>;
}) {
  return (
    <div className="space-y-4">
      <section className="card p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-bold text-slate-900">Best gains</h2>
            <p className="mt-1 text-xs text-slate-500">
              run_id <span className="font-mono text-slate-700">{result.run_id}</span>
            </p>
          </div>
          <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700">
            Saved to history
          </span>
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          {Object.entries(result.controller_parameters).map(([name, value]) => (
            <div key={name} className="rounded-xl bg-slate-50 px-3 py-3">
              <p className="label">{name}</p>
              <p className="mt-1 font-mono text-xl font-bold text-slate-900">
                {formatNumber(value, 4)}
              </p>
            </div>
          ))}
        </div>
        <div className="mt-4">
          <StopReasonBadge stopReason={result.stop_reason} />
        </div>
        <div className="mt-4 flex flex-wrap gap-4 text-sm text-slate-600">
          <span>
            Evaluations: <strong>{result.num_evaluations}</strong>
          </span>
          <span>
            GA cost: <strong>{formatNumber(result.ga_cost)}</strong>
          </span>
          <span>
            Baseline cost: <strong>{formatNumber(result.baseline_cost)}</strong>
          </span>
          {result.target_hit?.generation !== null && result.target_hit?.generation !== undefined ? (
            <span>
              Target hit: generation <strong>{result.target_hit.generation}</strong> at NFE{" "}
              <strong>{result.target_hit.nfe}</strong>
            </span>
          ) : null}
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => exportGainsJson(result)}
            className="btn-secondary"
          >
            Export JSON
          </button>
          <button
            type="button"
            onClick={() => exportGainsCsv(result)}
            className="btn-secondary"
          >
            Export CSV
          </button>
        </div>
      </section>

      {result.warnings.length > 0 ? (
        <section className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
          <h3 className="font-semibold">Warnings</h3>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            {result.warnings.map((warning, index) => (
              <li key={`${warning}-${index}`}>{warning}</li>
            ))}
          </ul>
        </section>
      ) : null}

      <MetricsVsTargetsTable metrics={result.achieved_metrics} targets={targets} />
      <ProgressCharts progress={result.progress} />
    </div>
  );
}
