import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type Progress = Record<string, unknown[]>;

function numberAt(progress: Progress, key: string, index: number): number | null {
  const series = progress[key];
  const value = Array.isArray(series) ? series[index] : undefined;
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function chooseSeries(progress: Progress, keys: string[], length: number): Array<number | null> {
  for (const key of keys) {
    if (Array.isArray(progress[key])) {
      return Array.from({ length }, (_, index) => numberAt(progress, key, index));
    }
  }
  return Array.from({ length }, () => null);
}

function chartLength(progress: Progress): number {
  const keys = ["iteration", "best_cost", "best_ga_cost", "Kp", "success_score"];
  return keys.reduce((max, key) => {
    const value = progress[key];
    return Array.isArray(value) ? Math.max(max, value.length) : max;
  }, 0);
}

function ChartShell({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="card p-4 sm:p-5">
      <h3 className="text-base font-bold text-slate-900">{title}</h3>
      <div className="mt-3 h-[240px] w-full">{children}</div>
    </section>
  );
}

export function ProgressCharts({ progress }: { progress: Progress }) {
  const length = chartLength(progress);
  if (length === 0) {
    return (
      <section className="card p-5 text-sm text-slate-500">
        This run did not persist progress history.
      </section>
    );
  }

  const iterations = chooseSeries(progress, ["iteration"], length).map((value, index) =>
    value ?? index + 1,
  );
  const costs = iterations.map((iteration, index) => ({
    iteration,
    best: numberAt(progress, "best_cost", index) ?? numberAt(progress, "best_ga_cost", index),
    mean: numberAt(progress, "mean_cost", index) ?? numberAt(progress, "mean_ga_cost", index),
  }));
  const gains = iterations.map((iteration, index) => ({
    iteration,
    Kp: numberAt(progress, "Kp", index),
    Ki: numberAt(progress, "Ki", index),
    Kd: numberAt(progress, "Kd", index),
  }));
  const scores = iterations.map((iteration, index) => ({
    iteration,
    success_score: numberAt(progress, "success_score", index),
    best_score_so_far: numberAt(progress, "best_score_so_far", index),
  }));

  return (
    <div className="space-y-4">
      <ChartShell title="Cost history">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={costs} margin={{ top: 8, right: 16, bottom: 4, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="iteration" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} width={56} />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="best" name="Best cost" stroke="#2563eb" dot={false} isAnimationActive={false} />
            <Line type="monotone" dataKey="mean" name="Mean cost" stroke="#94a3b8" dot={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </ChartShell>

      <ChartShell title="Gain history">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={gains} margin={{ top: 8, right: 16, bottom: 4, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="iteration" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} width={56} />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="Kp" stroke="#2563eb" dot={false} isAnimationActive={false} />
            <Line type="monotone" dataKey="Ki" stroke="#db2777" dot={false} isAnimationActive={false} />
            <Line type="monotone" dataKey="Kd" stroke="#059669" dot={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </ChartShell>

      <ChartShell title="Success score">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={scores} margin={{ top: 8, right: 16, bottom: 4, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="iteration" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} width={56} />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="success_score" name="Success score" stroke="#6366f1" dot={false} isAnimationActive={false} />
            <Line type="monotone" dataKey="best_score_so_far" name="Best so far" stroke="#059669" dot={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </ChartShell>
    </div>
  );
}
