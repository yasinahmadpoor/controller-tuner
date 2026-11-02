import type { MetricName, Metrics } from "../../types/api";
import { formatMetric, metricLabel } from "../../lib/format";

export function MetricsVsTargetsTable({
  metrics,
  targets,
}: {
  metrics: Metrics;
  targets: Partial<Record<MetricName, number>>;
}) {
  const entries = Object.entries(targets).filter(
    (entry): entry is [MetricName, number] =>
      typeof entry[1] === "number" && Number.isFinite(entry[1]),
  );

  return (
    <section className="card p-4 sm:p-5">
      <h3 className="text-base font-bold text-slate-900">Achieved vs targets</h3>
      <div className="mt-3 overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
          <thead className="text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="py-2 pr-4 font-semibold">Metric</th>
              <th className="px-4 py-2 font-semibold">Achieved</th>
              <th className="px-4 py-2 font-semibold">Target</th>
              <th className="px-4 py-2 text-right font-semibold">Result</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {entries.map(([name, target]) => {
              const achieved = metrics[name];
              const numeric = typeof achieved === "number" && Number.isFinite(achieved);
              const hit = numeric && achieved <= target;
              return (
                <tr key={name}>
                  <td className="py-2 pr-4 text-slate-700">{metricLabel(name)}</td>
                  <td className="px-4 py-2 font-mono font-semibold text-slate-900">
                    {formatMetric(achieved)}
                  </td>
                  <td className="px-4 py-2 font-mono text-slate-600">{formatMetric(target)}</td>
                  <td className="px-4 py-2 text-right">
                    <span
                      className={[
                        "inline-flex rounded-full px-2.5 py-1 text-xs font-semibold",
                        hit
                          ? "bg-emerald-50 text-emerald-700"
                          : "bg-rose-50 text-rose-700",
                      ].join(" ")}
                    >
                      {hit ? "Hit" : "Miss"}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
