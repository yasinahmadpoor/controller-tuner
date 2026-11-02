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

export function ControlChart({
  timePoints,
  controlSignals,
}: {
  timePoints: number[];
  controlSignals: number[];
}) {
  const data = timePoints.map((time, index) => ({
    time,
    control: controlSignals[index],
  }));

  return (
    <section className="card p-4 sm:p-5">
      <h3 className="text-base font-bold text-slate-900">Control input</h3>
      <div className="mt-3 h-[240px] w-full">
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
            <Line
              type="monotone"
              dataKey="control"
              name="Control"
              stroke="#db2777"
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
