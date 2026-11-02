import { useState } from "react";

import type {
  MetricName,
  OptimizeResult,
  SystemSummary,
} from "../../types/api";
import { AutoTuneResults } from "../results/AutoTuneResults";
import { AutoTuneForm } from "./AutoTuneForm";

export function AutoTuneTab({ system }: { system: SystemSummary }) {
  const [result, setResult] = useState<OptimizeResult | null>(null);
  const [targets, setTargets] = useState<Partial<Record<MetricName, number>>>(
    system.optimization.fixed_targets,
  );

  if (!system.capabilities.includes("optimize")) {
    return (
      <section className="card p-6">
        <h2 className="text-lg font-bold text-slate-900">Auto-tune unavailable</h2>
        <p className="mt-2 max-w-2xl text-sm text-slate-600">
          This system was created without the <code className="font-mono">optimize</code>{" "}
          capability. Upload or define the system with a target, control limits, input and
          output channels, trim values, and trim initial conditions to enable GA tuning.
          Manual simulation remains available.
        </p>
      </section>
    );
  }

  return (
    <div className="space-y-6">
      <AutoTuneForm
        system={system}
        onOptimized={(nextResult, submittedTargets) => {
          setResult(nextResult);
          setTargets(submittedTargets);
        }}
      />
      {result ? (
        <AutoTuneResults result={result} targets={targets} />
      ) : (
        <section className="card grid min-h-[240px] place-items-center p-8 text-center">
          <div>
            <p className="text-lg font-bold text-slate-800">No optimization yet</p>
            <p className="mt-2 max-w-sm text-sm text-slate-500">
              Configure the search space and run the GA to see best gains, achieved metrics,
              stop reason, and progress history.
            </p>
          </div>
        </section>
      )}
    </div>
  );
}
