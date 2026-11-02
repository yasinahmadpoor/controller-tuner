import { formatMetric, metricLabel } from "../../lib/format";
import type { Metrics } from "../../types/api";

export function MetricsPanel({
  metrics,
  nonFiniteMetrics = [],
}: {
  metrics: Metrics;
  nonFiniteMetrics?: string[];
}) {
  const entries = Object.entries(metrics).filter(
    ([key, value]) => key !== "stable" && (typeof value === "number" || value === null),
  ) as Array<[string, number | null]>;

  return (
    <section className="card p-4 sm:p-5">
      <h3 className="text-base font-bold text-slate-900">Metrics</h3>
      <dl className="mt-3 grid gap-3 sm:grid-cols-2">
        {entries.map(([key, value]) => {
          const nonFinite = value === null || nonFiniteMetrics.includes(key);
          return (
            <div
              key={key}
              className="flex items-center justify-between gap-3 rounded-xl bg-slate-50 px-3 py-2"
            >
              <dt className="text-sm text-slate-600">{metricLabel(key)}</dt>
              <dd
                title={nonFinite ? "Non-finite value from the engine" : undefined}
                className="font-mono text-sm font-semibold text-slate-900"
              >
                {formatMetric(value)}
              </dd>
            </div>
          );
        })}
      </dl>
    </section>
  );
}
