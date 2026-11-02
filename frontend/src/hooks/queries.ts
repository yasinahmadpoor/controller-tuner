import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import {
  deleteRun,
  getCatalog,
  getRun,
  getSchema,
  getSystem,
  listOptimizations,
  listSimulations,
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
const systemKey = (systemId: string) => ["system", systemId] as const;
const schemaKey = (systemId: string, type: ControllerType) =>
  ["schema", systemId, type] as const;
const runsKey = (systemId: string, type: RunType) =>
  ["runs", systemId, type] as const;
const runKey = (runId: string, type: RunType) => ["run", runId, type] as const;

export function useCatalog() {
  return useQuery({
    queryKey: catalogKey,
    queryFn: getCatalog,
    staleTime: 60_000,
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
