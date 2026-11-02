import type { SystemSummary } from "../../types/api";

export function SystemSummaryCard({ system }: { system: SystemSummary }) {
  return (
    <section className="card overflow-hidden">
      <div className="bg-gradient-to-br from-accent-600 to-accent-700 px-5 py-5 text-white sm:px-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-accent-100">
              Active system
            </p>
            <h1 className="mt-1 text-2xl font-black tracking-tight">{system.name}</h1>
            {system.objective ? (
              <p className="mt-1 max-w-2xl text-sm text-accent-100">{system.objective}</p>
            ) : null}
          </div>
          <div className="flex flex-wrap gap-2">
            {system.capabilities.map((capability) => (
              <span
                key={capability}
                className="rounded-full bg-white/15 px-2.5 py-1 text-xs font-semibold capitalize"
              >
                {capability}
              </span>
            ))}
          </div>
        </div>
      </div>
      <dl className="grid grid-cols-2 gap-4 px-5 py-4 text-sm sm:grid-cols-4 sm:px-6">
        <div>
          <dt className="label">States</dt>
          <dd className="mt-1 font-semibold text-slate-900">{system.num_states}</dd>
        </div>
        <div>
          <dt className="label">Inputs</dt>
          <dd className="mt-1 font-semibold text-slate-900">{system.num_inputs}</dd>
        </div>
        <div>
          <dt className="label">Target</dt>
          <dd className="mt-1 font-semibold text-slate-900">{system.target}</dd>
        </div>
        <div>
          <dt className="label">Step</dt>
          <dd className="mt-1 font-semibold text-slate-900">{system.simulation.dt}s</dd>
        </div>
      </dl>
    </section>
  );
}
