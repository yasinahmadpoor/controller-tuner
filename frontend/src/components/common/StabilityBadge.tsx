export function StabilityBadge({ stable }: { stable: boolean | null | undefined }) {
  if (stable === null || stable === undefined) {
    return (
      <span className="inline-flex rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-600">
        Unknown
      </span>
    );
  }
  return (
    <span
      className={[
        "inline-flex rounded-full px-2.5 py-1 text-xs font-semibold",
        stable ? "bg-emerald-100 text-emerald-800" : "bg-rose-100 text-rose-800",
      ].join(" ")}
    >
      {stable ? "Stable" : "Unstable"}
    </span>
  );
}
