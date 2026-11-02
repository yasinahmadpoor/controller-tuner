import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import {
  cancelJob,
  deleteRun,
  deleteSystem,
  enqueueOptimize,
  getCatalog,
  getJob,
  getRun,
  getSchema,
  getSystem,
  listOptimizations,
  listSimulations,
  listSystems,
  optimize,
  simulate,
  uploadSystem,
} from "../api/client";
import type {
  ControllerType,
  OptimizeRequest,
  RunType,
  SimulateRequest,
} from "../types/api";

const catalogKey = ["catalog"] as const;
const systemsKey = ["systems"] as const;
const systemKey = (systemId: string) => ["system", systemId] as const;
const schemaKey = (systemId: string, type: ControllerType) =>
  ["schema", systemId, type] as const;
const runsKey = (systemId: string, type: RunType) =>
  ["runs", systemId, type] as const;
const runKey = (runId: string, type: RunType) => ["run", runId, type] as const;
const jobKey = (jobId: string) => ["job", jobId] as const;

export function useCatalog() {
  return useQuery({
    queryKey: catalogKey,
    queryFn: getCatalog,
    staleTime: 60_000,
  });
}

export function useSystems(
  params: { limit?: number; offset?: number; source_type?: string; source_ref?: string } = {},
) {
  return useQuery({
    queryKey: [...systemsKey, params] as const,
    queryFn: () => listSystems(params),
    staleTime: 15_000,
  });
}

export function useDeleteSystem() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (systemId: string) => deleteSystem(systemId),
    onSuccess: (_data, systemId) => {
      queryClient.removeQueries({ queryKey: systemKey(systemId) });
      void queryClient.invalidateQueries({ queryKey: systemsKey });
      void queryClient.invalidateQueries({ queryKey: catalogKey });
    },
  });
}

export function useSystem(systemId: string | undefined) {
  return useQuery({
    queryKey: systemKey(systemId ?? ""),
    queryFn: () => getSystem(systemId as string),
    enabled: Boolean(systemId),
  });
}

export function useSchema(
  systemId: string | undefined,
  controllerType: ControllerType,
) {
  return useQuery({
    queryKey: schemaKey(systemId ?? "", controllerType),
    queryFn: () => getSchema(systemId as string, controllerType),
    enabled: Boolean(systemId),
    staleTime: 60_000,
  });
}

export function useSimulate(systemId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: SimulateRequest) => simulate(systemId, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: runsKey(systemId, "simulation") });
    },
  });
}

export function useOptimize(systemId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: OptimizeRequest) => optimize(systemId, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: runsKey(systemId, "optimization"),
      });
    },
  });
}

export function useEnqueueOptimize(systemId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: OptimizeRequest) => enqueueOptimize(systemId, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: runsKey(systemId, "optimization"),
      });
    },
  });
}

export function useJob(jobId: string | undefined) {
  return useQuery({
    queryKey: jobKey(jobId ?? ""),
    queryFn: () => getJob(jobId as string),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "succeeded" || status === "failed" || status === "cancelled"
        ? false
        : 1_000;
    },
  });
}

export function useCancelJob(jobId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => cancelJob(jobId as string),
    onSuccess: (job) => {
      queryClient.setQueryData(jobKey(job.job_id), job);
    },
  });
}

export function useCreateSystem() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { file: File; metadata: Record<string, unknown> }) =>
      uploadSystem(input.file, input.metadata),
    onSuccess: (system) => {
      queryClient.setQueryData(systemKey(system.system_id), system);
    },
  });
}

export function useSystemRuns(
  systemId: string | undefined,
  type: RunType,
  limit = 20,
  offset = 0,
) {
  return useQuery({
    queryKey: [...runsKey(systemId ?? "", type), limit, offset] as const,
    queryFn: () =>
      type === "simulation"
        ? listSimulations(systemId as string, limit, offset)
        : listOptimizations(systemId as string, limit, offset),
    enabled: Boolean(systemId),
    placeholderData: (previous) => previous,
  });
}

export function useOptimizationRuns(
  systemId: string | undefined,
  limit = 20,
  offset = 0,
) {
  return useSystemRuns(systemId, "optimization", limit, offset);
}

export function useRun(
  runId: string | undefined,
  type: RunType,
  options: { enabled?: boolean } = {},
) {
  return useQuery({
    queryKey: runKey(runId ?? "", type),
    queryFn: () => getRun(runId as string, type),
    enabled: Boolean(runId) && (options.enabled ?? true),
  });
}

export function useDeleteRun(systemId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { runId: string; type: RunType }) =>
      deleteRun(input.runId, input.type),
    onSuccess: (_data, input) => {
      void queryClient.invalidateQueries({ queryKey: runsKey(systemId, input.type) });
      queryClient.removeQueries({ queryKey: runKey(input.runId, input.type) });
    },
  });
}
