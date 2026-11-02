import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export interface TrajectoryChartProps {
  timePoints: number[];
  trajectory: number[];
  target: number;
}

export function TrajectoryChart({ timePoints, trajectory, target }: TrajectoryChartProps) {
  const data = timePoints.map((time, index) => ({
    time,
    response: trajectory[index],
  }));

  return (
    <section className="card p-4 sm:p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-base font-bold text-slate-900">System response</h3>
        <span className="text-xs font-semibold text-slate-500">
          Target {target}
        </span>
      </div>
      <p className="sr-only">Target reference: {target}</p>
      <div className="mt-3 h-[280px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 16, bottom: 4, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis
              dataKey="time"
              tickFormatter={(value: number) => value.toFixed(2)}
              tick={{ fontSize: 11 }}
            />
            <YAxis tick={{ fontSize: 11 }} width={48} />
            <Tooltip
              formatter={(value: number) => value.toFixed(4)}
              labelFormatter={(value: number) => `t = ${Number(value).toFixed(3)}s`}
            />
            <Legend />
            <ReferenceLine
              y={target}
              stroke="#059669"
              strokeDasharray="6 4"
              label={{ value: "Target", position: "insideTopRight", fill: "#059669" }}
            />
            <Line
              type="monotone"
              dataKey="response"
              name="Response"
              stroke="#2563eb"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
