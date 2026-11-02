import type {
  CatalogResponse,
  ControllerType,
  OptimizationRunDetail,
  JobResponse,
  OptimizeJobResponse,
  OptimizeRequest,
  OptimizeResult,
  ParamSchemaResponse,
  RunDetail,
  RunListResponse,
  SimulateRequest,
  SimulateResult,
  SimulationRunDetail,
  SystemSummary,
} from "../types/api";

const API_BASE = import.meta.env.VITE_API_URL ?? "/api/v1";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly context: Record<string, unknown>;

  constructor(
    status: number,
    code = "network_error",
    message = "Request failed",
    context: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.context = context;
  }
}

interface ErrorBody {
  error?: {
    code?: string;
    message?: string;
    context?: Record<string, unknown>;
  };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (!(init?.body instanceof FormData) && init?.body !== undefined) {
    headers.set("Content-Type", "application/json");
  }
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, { ...init, headers });
  } catch (error) {
    throw new ApiError(
      0,
      "network_error",
      error instanceof Error ? error.message : "Unable to reach the backend.",
    );
  }
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as ErrorBody | null;
    throw new ApiError(
      response.status,
      body?.error?.code ?? "http_error",
      body?.error?.message ?? `Request failed with status ${response.status}`,
      body?.error?.context ?? {},
    );
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export function getCatalog(): Promise<CatalogResponse> {
  return request<CatalogResponse>("/catalog");
}

export function createSystemFromCatalog(catalogId: string): Promise<SystemSummary> {
  return request<SystemSummary>("/systems", {
    method: "POST",
    body: JSON.stringify({ source: { type: "catalog", catalog_id: catalogId } }),
  });
}

export function uploadSystem(
  file: File,
  metadata: Record<string, unknown>,
): Promise<SystemSummary> {
  const body = new FormData();
  body.append("file", file);
  body.append("metadata", JSON.stringify(metadata));
  return request<SystemSummary>("/systems", { method: "POST", body });
}

export function getSystem(systemId: string): Promise<SystemSummary> {
  return request<SystemSummary>(`/systems/${systemId}`);
}

export function getSchema(
  systemId: string,
  controllerType: ControllerType,
): Promise<ParamSchemaResponse> {
  return request<ParamSchemaResponse>(
    `/systems/${systemId}/schema?controller_type=${encodeURIComponent(controllerType)}`,
  );
}

export function simulate(
  systemId: string,
  payload: SimulateRequest,
): Promise<SimulateResult> {
  return request<SimulateResult>(`/systems/${systemId}/simulate`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listSimulations(
  systemId: string,
  limit = 20,
  offset = 0,
): Promise<RunListResponse> {
  return request<RunListResponse>(
    `/systems/${systemId}/simulations?limit=${limit}&offset=${offset}`,
  );
}

export function getSimulationRun(runId: string): Promise<SimulationRunDetail> {
  return request<SimulationRunDetail>(
    `/simulations/${runId}?include_artifacts=true`,
  );
}

export function deleteSimulationRun(runId: string): Promise<void> {
  return request<void>(`/simulations/${runId}`, { method: "DELETE" });
}

export function optimize(
  systemId: string,
  payload: OptimizeRequest,
): Promise<OptimizeResult> {
  return request<OptimizeResult>(`/systems/${systemId}/optimize`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function enqueueOptimize(
  systemId: string,
  payload: OptimizeRequest,
): Promise<OptimizeJobResponse> {
  return request<OptimizeJobResponse>(`/systems/${systemId}/optimize`, {
    method: "POST",
    body: JSON.stringify({ ...payload, async: true }),
  });
}

export function getJob(jobId: string): Promise<JobResponse> {
  return request<JobResponse>(`/jobs/${jobId}`);
}

export function cancelJob(jobId: string): Promise<JobResponse> {
  return request<JobResponse>(`/jobs/${jobId}/cancel`, { method: "POST" });
}

export function jobEventsUrl(jobId: string): string {
  return `${API_BASE}/jobs/${jobId}/events`;
}

export function listOptimizations(
  systemId: string,
  limit = 20,
  offset = 0,
): Promise<RunListResponse> {
  return request<RunListResponse>(
    `/systems/${systemId}/optimizations?limit=${limit}&offset=${offset}`,
  );
}

export function getOptimizationRun(runId: string): Promise<OptimizationRunDetail> {
  return request<OptimizationRunDetail>(`/optimizations/${runId}`);
}

export function deleteOptimizationRun(runId: string): Promise<void> {
  return request<void>(`/optimizations/${runId}`, { method: "DELETE" });
}

export function getRun(
  runId: string,
  type: "simulation" | "optimization",
): Promise<RunDetail> {
  return type === "simulation"
    ? getSimulationRun(runId)
    : getOptimizationRun(runId);
}

export function deleteRun(
  runId: string,
  type: "simulation" | "optimization",
): Promise<void> {
  return type === "simulation"
    ? deleteSimulationRun(runId)
    : deleteOptimizationRun(runId);
}

export { API_BASE };
