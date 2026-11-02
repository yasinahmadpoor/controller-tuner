import type { ReactNode } from "react";

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="rounded-xl border border-dashed border-slate-300 bg-white/70 px-6 py-10 text-center">
      <p className="font-medium text-slate-800">{title}</p>
      {children ? <div className="mt-2 text-sm text-slate-500">{children}</div> : null}
    </div>
  );
}
