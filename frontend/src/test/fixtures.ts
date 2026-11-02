import type {
  CatalogEntry,
  JobResponse,
  OptimizationRunDetail,
  OptimizeJobResponse,
  OptimizeResult,
  ParamSchemaResponse,
  RunSummary,
  SimulateResult,
  SystemSummary,
} from "../types/api";

export const catalogEntry: CatalogEntry = {
  catalog_id: "ball_beam",
  name: "Ball Beam",
  description: "Balance a ball on a beam",
  objective: "Track the target position",
  num_states: 2,
  num_inputs: 1,
  target: 0,
  capabilities: ["simulate", "optimize"],
  sources: { json: "BallBeam.json", python: "BallBeam.py" },
};

export const systemFixture: SystemSummary = {
  system_id: "11111111-1111-1111-1111-111111111111",
  name: "Ball Beam",
  description: "Balance a ball on a beam",
  objective: "Track the target position",
  source_type: "catalog_json",
  source_ref: "ball_beam",
  num_states: 2,
  num_inputs: 1,
  target: 0,
  capabilities: ["simulate", "optimize"],
  simulation: {
    dt: 0.01,
    max_time: 1,
    target: 0,
    input_channel: 0,
    output_channel: 0,
    trim_values: [0],
    trim_ics: [1, 0],
    min_control: -0.5,
    max_control: 0.5,
    initial_condition_range: [-1, 1],
    randomness_level: 0,
    disturbance_level: 0,
  },
  optimization: {
    param_ranges: {
      Kp: [1, 50],
      Ki: [0.01, 5],
      Kd: [0.01, 10],
    },
    weights: { mse: 1, settling_time: 0.5, overshoot: 0.5, control_effort: 0.1 },
    fixed_targets: { mse: 0.05, settling_time: 1, overshoot: 1, control_effort: 0.1 },
    ga: { population_size: 20, generations: 30, seed: 42, max_wall_clock: 120 },
  },
  created_at: "2026-01-01T00:00:00Z",
};

export const schemaFixture: ParamSchemaResponse = {
  controller_type: "PID",
  params: {
    Kp: { min: 0.1, max: 60 },
    Ki: { min: 0, max: 5 },
    Kd: { min: 0, max: 20 },
  },
};

export const simulateResultFixture: SimulateResult = {
  success: true,
  run_id: "22222222-2222-2222-2222-222222222222",
  engine: "manual_tuner",
  controller_type: "PID",
  params: { Kp: 15, Ki: 0.5, Kd: 2 },
  time_points: [0, 0.5, 1],
  trajectory: [1, 0.4, 0.1],
  control_signals: [0, -0.2, -0.05],
  metrics: {
    mse: 0.03,
    settling_time: null,
    overshoot: 4.2,
    control_effort: 0.08,
    stable: true,
  },
  non_finite_metrics: ["settling_time"],
};

export const simulationRun: RunSummary = {
  run_id: simulateResultFixture.run_id,
  system_id: systemFixture.system_id,
  run_type: "simulation",
  engine: "manual_tuner",
  controller_type: "PID",
  status: "succeeded",
  created_at: "2026-01-01T00:00:00Z",
  duration_ms: 12,
  summary: { mse: 0.03, settling_time: null, stable: true },
};

export const optimizationRun: RunSummary = {
  run_id: "33333333-3333-3333-3333-333333333333",
  system_id: systemFixture.system_id,
  run_type: "optimization",
  engine: "ga_tuner",
  status: "succeeded",
  created_at: "2026-01-02T00:00:00Z",
  duration_ms: 2000,
  stop_reason: "normal",
  best_params: { Kp: 20.5, Ki: 0.3, Kd: 9.7 },
  summary: { mse: 0.02, settling_time: 1.1, overshoot: 0 },
};


export const optimizeResultFixture: OptimizeResult = {
  success: true,
  run_id: optimizationRun.run_id,
  engine: "ga_tuner",
  controller_parameters: { Kp: 20.5932, Ki: 0.2998, Kd: 9.6994 },
  achieved_metrics: {
    mse: 0.04,
    settling_time: 0.9,
    overshoot: 2.1,
    control_effort: 0.08,
    stable: true,
  },
  ga_cost: 0.7469,
  baseline_cost: 13.4471,
  progress: {
    iteration: [1, 2],
    best_cost: [0.9, 0.7469],
    mean_cost: [315.47, 28.36],
    Kp: [20.5932, 20.5932],
    Ki: [0.2998, 0.2998],
    Kd: [9.6994, 9.6994],
    success_score: [50, 50],
    best_score_so_far: [50, 50],
  },
  stop_reason: "normal",
  num_evaluations: 16,
  target_hit: { nfe: null, time: null, generation: null },
  warnings: [],
  non_finite_metrics: [],
};

export const optimizationDetailFixture: OptimizationRunDetail = {
  run_id: optimizationRun.run_id,
  system_id: systemFixture.system_id,
  run_type: "optimization",
  engine: "ga_tuner",
  status: "succeeded",
  request: { fixed_targets: { ...systemFixture.optimization.fixed_targets } },
  controller_parameters: optimizeResultFixture.controller_parameters,
  best_params: optimizeResultFixture.controller_parameters,
  achieved_metrics: optimizeResultFixture.achieved_metrics,
  progress: optimizeResultFixture.progress,
  stop_reason: "normal",
  num_evaluations: 16,
  target_hit: { nfe: null, time: null, generation: null },
  warnings: [],
  non_finite_metrics: [],
  ga_cost: 0.7469,
  baseline_cost: 13.4471,
  error: null,
  duration_ms: 2000,
  created_at: "2026-01-02T00:00:00Z",
  started_at: "2026-01-02T00:00:00Z",
  finished_at: "2026-01-02T00:00:02Z",
};


export const optimizeJobFixture: OptimizeJobResponse = {
  job_id: "44444444-4444-4444-4444-444444444444",
  run_id: optimizationRun.run_id,
  status: "queued",
  links: {
    self: "/api/v1/jobs/44444444-4444-4444-4444-444444444444",
    events: "/api/v1/jobs/44444444-4444-4444-4444-444444444444/events",
    run: `/api/v1/optimizations/${optimizationRun.run_id}`,
  },
};

export const runningJobFixture: JobResponse = {
  job_id: optimizeJobFixture.job_id,
  run_id: optimizeJobFixture.run_id,
  system_id: systemFixture.system_id,
  status: "running",
  progress: {
    generation: 12,
    cumulative_nfe: 480,
    cumulative_wall_time: 9.4,
    best_score_so_far: 75,
    Kp: 14.2,
    Ki: 0.31,
    Kd: 5.6,
  },
  cancel_requested: false,
  result: null,
  error: null,
  worker_id: "worker-1",
  created_at: "2026-01-02T00:00:00Z",
  started_at: "2026-01-02T00:00:00Z",
  finished_at: null,
  expires_at: null,
};
