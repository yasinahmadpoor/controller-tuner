export type ControllerType = "P" | "PI" | "PD" | "PID" | "FSF";
export type Capability = "simulate" | "optimize";
export type RunType = "simulation" | "optimization";
export type MetricName =
  | "mse"
  | "settling_time"
  | "overshoot"
  | "control_effort";

export interface CatalogEntry {
  catalog_id: string;
  name: string;
  description: string | null;
  objective: string | null;
  num_states: number;
  num_inputs: number;
  target: number;
  capabilities: Capability[];
  sources: Record<string, string>;
}

export interface CatalogResponse {
  items: CatalogEntry[];
}

export interface SimulationDefaults {
  dt: number;
  max_time: number;
  target: number;
  input_channel: number;
  output_channel: number;
  trim_values: number[];
  trim_ics: number[] | null;
  min_control: number;
  max_control: number;
  initial_condition_range: [number, number];
  randomness_level: number;
  disturbance_level: number;
}

export interface OptimizationDefaults {
  param_ranges: Record<string, [number, number]>;
  weights: Partial<Record<MetricName, number>>;
  fixed_targets: Partial<Record<MetricName, number>>;
  ga: {
    population_size: number;
    generations: number;
    seed: number | null;
    max_wall_clock: number;
  };
}

export interface SystemSummary {
  system_id: string;
  name: string;
  description: string | null;
  objective: string | null;
  source_type: string;
  source_ref: string | null;
  num_states: number;
  num_inputs: number;
  target: number;
  capabilities: Capability[];
  simulation: SimulationDefaults;
  optimization: OptimizationDefaults;
  created_at: string;
}

export interface SystemListResponse {
  items: SystemSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface ParamBounds {
  min: number;
  max: number;
}

export interface ParamSchemaResponse {
  controller_type: ControllerType;
  params: Record<string, ParamBounds>;
}

export interface SimulationOverrides {
  dt?: number;
  max_time?: number;
  target?: number;
  input_channel?: number;
  output_channel?: number;
  trim_values?: number[];
  min_control?: number;
  max_control?: number;
  initial_condition_range?: [number, number];
  randomness_level?: number;
  disturbance_level?: number;
}

export interface SimulateRequest {
  controller_type: ControllerType;
  params: Record<string, number>;
  initial_state?: number[] | null;
  seed?: number | null;
  overrides?: SimulationOverrides | null;
}

export interface SimulateResult {
  success: boolean;
  run_id: string;
  engine: "manual_tuner";
  controller_type: ControllerType;
  params: Record<string, number>;
  time_points: number[];
  trajectory: number[];
  control_signals: number[];
  metrics: Metrics;
  non_finite_metrics: string[];
}

export type MetricValue = number | null;

export interface Metrics {
  mse?: MetricValue;
  settling_time?: MetricValue;
  overshoot?: MetricValue;
  control_effort?: MetricValue;
  rise_time?: MetricValue;
  steady_state_error?: MetricValue;
  control_zero_crossings?: MetricValue;
  stable?: boolean | null;
  [key: string]: MetricValue | boolean | undefined;
}

export interface RunSummary {
  run_id: string;
  system_id: string;
  run_type: RunType;
  engine: string;
  status: string;
  created_at: string;
  duration_ms?: number | null;
  summary?: Record<string, MetricValue | boolean>;
  controller_type?: ControllerType;
  stop_reason?: string | null;
  best_params?: Record<string, number>;
}

export interface RunListResponse {
  items: RunSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface TrajectoryPayload {
  time_points: number[];
  trajectory: number[];
  control_signals: number[];
}

export interface SimulationRunDetail {
  run_id: string;
  system_id: string;
  run_type: "simulation";
  engine: string;
  controller_type: ControllerType;
  status: string;
  request: Record<string, unknown> | null;
  params: Record<string, number>;
  overrides: Record<string, unknown>;
  initial_state: number[] | null;
  seed: number | null;
  metrics: Metrics;
  non_finite_metrics: string[];
  warnings: string[];
  error: { type?: string; message?: string } | null;
  duration_ms: number | null;
  created_at: string;
  trajectory: TrajectoryPayload | null;
}

export interface TargetHit {
  nfe: number | null;
  time: number | null;
  generation: number | null;
}

export interface OptimizeRequest {
  param_ranges?: Record<string, [number, number]>;
  weights?: Partial<Record<MetricName, number>>;
  fixed_targets?: Partial<Record<MetricName, number>>;
  ga_config?: {
    population_size: number;
    generations: number;
    seed: number | null;
    max_wall_clock: number;
  };
  async?: false;
}

export interface OptimizeResult {
  success: boolean;
  run_id: string;
  engine: "ga_tuner";
  controller_parameters: Record<string, number>;
  achieved_metrics: Metrics;
  ga_cost: number | null;
  baseline_cost: number | null;
  progress: Record<string, unknown[]>;
  stop_reason: "normal" | "score_100" | "wall_clock";
  num_evaluations: number;
  target_hit: TargetHit;
  warnings: string[];
  non_finite_metrics: string[];
}

export type JobStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";

export interface JobLinks {
  self: string;
  events: string;
  run: string;
}

export interface OptimizeJobResponse {
  job_id: string;
  run_id: string;
  status: JobStatus;
  links: JobLinks;
}

export interface JobResponse {
  job_id: string;
  run_id: string;
  system_id: string | null;
  status: JobStatus;
  progress: Record<string, unknown>;
  cancel_requested: boolean;
  result: OptimizeResult | null;
  error: { type?: string; message?: string } | null;
  worker_id: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  expires_at: string | null;
}

export interface OptimizationRunDetail {
  run_id: string;
  system_id: string;
  run_type: "optimization";
  engine: string;
  status: string;
  request: Record<string, unknown>;
  controller_parameters: Record<string, number>;
  best_params: Record<string, number>;
  achieved_metrics: Metrics;
  progress: Record<string, unknown[]>;
  stop_reason: string | null;
  num_evaluations: number | null;
  target_hit: TargetHit | null;
  warnings: string[];
  non_finite_metrics: string[];
  ga_cost: number | null;
  baseline_cost: number | null;
  error: { type?: string; message?: string } | null;
  duration_ms: number | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export type RunDetail = SimulationRunDetail | OptimizationRunDetail;
