import type { ReactNode } from "react";

interface ErrorBannerProps {
  title?: string;
  message: ReactNode;
  onDismiss?: () => void;
}

export function ErrorBanner({ title = "Something went wrong", message, onDismiss }: ErrorBannerProps) {
  return (
    <div
      role="alert"
      className="flex items-start gap-3 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-900"
    >
      <div className="flex-1">
        <p className="font-semibold">{title}</p>
        <div className="mt-1 text-rose-800">{message}</div>
      </div>
      {onDismiss ? (
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Dismiss error"
          className="rounded-md px-2 py-1 text-rose-700 hover:bg-rose-100"
        >
          ×
        </button>
      ) : null}
    </div>
  );
}
