interface PaginationProps {
  total: number;
  limit: number;
  offset: number;
  onOffsetChange: (offset: number) => void;
}

export function Pagination({ total, limit, offset, onOffsetChange }: PaginationProps) {
  const start = total === 0 ? 0 : offset + 1;
  const end = Math.min(offset + limit, total);
  const canGoBack = offset > 0;
  const canGoForward = offset + limit < total;

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-slate-600">
      <span>
        Showing {start}–{end} of {total}
      </span>
      <div className="flex gap-2">
        <button
          type="button"
          disabled={!canGoBack}
          onClick={() => onOffsetChange(Math.max(0, offset - limit))}
          className="rounded-lg border border-slate-300 px-3 py-1.5 font-medium disabled:cursor-not-allowed disabled:opacity-40"
        >
          Previous
        </button>
        <button
          type="button"
          disabled={!canGoForward}
          onClick={() => onOffsetChange(offset + limit)}
          className="rounded-lg border border-slate-300 px-3 py-1.5 font-medium disabled:cursor-not-allowed disabled:opacity-40"
        >
          Next
        </button>
      </div>
    </div>
  );
}
