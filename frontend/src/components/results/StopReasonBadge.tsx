const copy: Record<string, { label: string; description: string; tone: string }> = {
  normal: {
    label: "Normal",
    description: "Completed the configured number of generations.",
    tone: "bg-slate-100 text-slate-700",
  },
  score_100: {
    label: "Score 100",
    description: "All configured targets were met.",
    tone: "bg-emerald-100 text-emerald-800",
  },
  wall_clock: {
    label: "Wall clock",
    description: "Stopped when the wall-clock budget was exhausted.",
    tone: "bg-amber-100 text-amber-900",
  },
};

export function StopReasonBadge({ stopReason }: { stopReason: string | null }) {
  const reason = stopReason ?? "normal";
  const entry = copy[reason] ?? {
    label: reason,
    description: "The engine stopped for an unknown reason.",
    tone: "bg-slate-100 text-slate-700",
  };
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${entry.tone}`}>
        {entry.label}
      </span>
      <span className="text-xs text-slate-500">{entry.description}</span>
    </div>
  );
}
