import type {
  CatalogEntry,
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
    fixed_targets: { mse: 0.1, settling_time: 3, overshoot: 10, control_effort: 0.1 },
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
  summary: { mse: 0.02, settling_time: 1.1, overshoot: 0 },
};
