import type { OptimizeResult } from "../types/api";

function filename(prefix: string, extension: string): string {
  return `${prefix}-${new Date().toISOString().replace(/[:.]/g, "-")}.${extension}`;
}

function download(content: string, name: string, type: string): void {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export function exportGainsJson(result: OptimizeResult): void {
  download(
    JSON.stringify(result.controller_parameters, null, 2),
    filename("gains", "json"),
    "application/json",
  );
}

export function exportGainsCsv(result: OptimizeResult): void {
  const lines = [
    "parameter,value",
    ...Object.entries(result.controller_parameters).map(
      ([name, value]) => `${name},${value}`,
    ),
  ];
  download(lines.join("\n"), filename("gains", "csv"), "text/csv");
}
