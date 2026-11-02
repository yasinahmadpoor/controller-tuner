import type { SimulateResult } from "../../types/api";
import { StabilityBadge } from "../common/StabilityBadge";
import { ControlChart } from "./ControlChart";
import { MetricsPanel } from "./MetricsPanel";
import { TrajectoryChart } from "./TrajectoryChart";

export function ManualResults({
  result,
  target,
}: {
  result: SimulateResult;
  target: number;
}) {
  return (
    <div className="space-y-4">
      <div className="card flex flex-wrap items-center justify-between gap-3 p-4 sm:p-5">
        <div>
          <h2 className="text-lg font-bold text-slate-900">Results</h2>
          <p className="mt-1 text-xs text-slate-500">
            run_id <span className="font-mono text-slate-700">{result.run_id}</span>
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700">
            Saved to history
          </span>
          <StabilityBadge stable={result.metrics.stable} />
        </div>
      </div>
      <TrajectoryChart
        timePoints={result.time_points}
        trajectory={result.trajectory}
        target={target}
      />
      <ControlChart timePoints={result.time_points} controlSignals={result.control_signals} />
      <MetricsPanel metrics={result.metrics} nonFiniteMetrics={result.non_finite_metrics} />
    </div>
  );
}
