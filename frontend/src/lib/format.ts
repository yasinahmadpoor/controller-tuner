import type { MetricValue } from "../types/api";

export function formatMetric(value: MetricValue | boolean | undefined): string {
  if (value === null || value === undefined) {
    return "∞";
  }
  if (typeof value === "boolean") {
    return value ? "Yes" : "No";
  }
  if (!Number.isFinite(value)) {
    return "∞";
  }
  if (Math.abs(value) >= 1000) {
    return value.toFixed(0);
  }
  if (Math.abs(value) >= 10) {
    return value.toFixed(2);
  }
  return value.toFixed(4);
}

export function formatNumber(value: number | null | undefined, digits = 3): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "—";
  }
  return value.toFixed(digits);
}

export function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export const METRIC_LABELS: Record<string, string> = {
  mse: "MSE",
  settling_time: "Settling time",
  overshoot: "Overshoot",
  control_effort: "Control effort",
  rise_time: "Rise time",
  steady_state_error: "Steady-state error",
  control_zero_crossings: "Control zero crossings",
};

export function metricLabel(key: string): string {
  return METRIC_LABELS[key] ?? key.replace(/_/g, " ");
}
