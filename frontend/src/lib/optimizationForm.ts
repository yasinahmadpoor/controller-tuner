import { z } from "zod";

import type {
  MetricName,
  OptimizeRequest,
  OptimizationDefaults,
  SystemSummary,
} from "../types/api";

export const GAIN_NAMES = ["Kp", "Ki", "Kd"] as const;
export const OPTIMIZATION_METRICS = [
  "mse",
  "settling_time",
  "overshoot",
  "control_effort",
] as const satisfies readonly MetricName[];

const rangeSchema = z
  .object({
    low: z.number({ invalid_type_error: "Enter a number" }),
    high: z.number({ invalid_type_error: "Enter a number" }),
  })
  .refine((range) => range.low < range.high, {
    message: "Low must be less than high",
    path: ["high"],
  });

const nonNegative = z
  .number({ invalid_type_error: "Enter a number" })
  .min(0, "Must be at least 0");
const positive = z
  .number({ invalid_type_error: "Enter a number" })
  .positive("Must be greater than 0");

export const optimizationFormSchema = z.object({
  ranges: z.object({
    Kp: rangeSchema,
    Ki: rangeSchema,
    Kd: rangeSchema,
  }),
  weights: z.object({
    mse: nonNegative,
    settling_time: nonNegative,
    overshoot: nonNegative,
    control_effort: nonNegative,
  }),
  fixed_targets: z.object({
    mse: positive,
    settling_time: positive,
    overshoot: positive,
    control_effort: positive,
  }),
  ga: z.object({
    population_size: z
      .number({ invalid_type_error: "Enter a number" })
      .int("Must be an integer")
      .min(5, "Population must be at least 5")
      .max(200, "Population must be at most 200"),
    generations: z
      .number({ invalid_type_error: "Enter a number" })
      .int("Must be an integer")
      .min(1, "Generations must be at least 1")
      .max(500, "Generations must be at most 500"),
    seed: z.number().int("Seed must be an integer").nullable(),
    max_wall_clock: z
      .number({ invalid_type_error: "Enter a number" })
      .min(1, "Wall clock must be at least 1 second")
      .max(600, "Wall clock must be at most 600 seconds"),
  }),
});

export type OptimizationFormValues = z.infer<typeof optimizationFormSchema>;

const FALLBACK_RANGES: Record<(typeof GAIN_NAMES)[number], [number, number]> = {
  Kp: [1, 50],
  Ki: [0.01, 5],
  Kd: [0.01, 10],
};

const FALLBACK_WEIGHTS: Record<MetricName, number> = {
  mse: 1,
  settling_time: 0.5,
  overshoot: 0.5,
  control_effort: 0.1,
};

const FALLBACK_TARGETS: Record<MetricName, number> = {
  mse: 0.1,
  settling_time: 3,
  overshoot: 10,
  control_effort: 0.1,
};

export function defaultsFromSystem(system: SystemSummary): OptimizationFormValues {
  const defaults: OptimizationDefaults = system.optimization;
  return {
    ranges: Object.fromEntries(
      GAIN_NAMES.map((name) => {
        const [low, high] = defaults.param_ranges?.[name] ?? FALLBACK_RANGES[name];
        return [name, { low, high }];
      }),
    ) as OptimizationFormValues["ranges"],
    weights: Object.fromEntries(
      OPTIMIZATION_METRICS.map((name) => [
        name,
        defaults.weights?.[name] ?? FALLBACK_WEIGHTS[name],
      ]),
    ) as OptimizationFormValues["weights"],
    fixed_targets: Object.fromEntries(
      OPTIMIZATION_METRICS.map((name) => [
        name,
        defaults.fixed_targets?.[name] ?? FALLBACK_TARGETS[name],
      ]),
    ) as OptimizationFormValues["fixed_targets"],
    ga: {
      population_size: defaults.ga?.population_size ?? 20,
      generations: defaults.ga?.generations ?? 30,
      seed: defaults.ga?.seed === undefined ? 42 : defaults.ga.seed,
      max_wall_clock: defaults.ga?.max_wall_clock ?? 120,
    },
  };
}

export function toOptimizeRequest(values: OptimizationFormValues): OptimizeRequest {
  return {
    param_ranges: {
      Kp: [values.ranges.Kp.low, values.ranges.Kp.high],
      Ki: [values.ranges.Ki.low, values.ranges.Ki.high],
      Kd: [values.ranges.Kd.low, values.ranges.Kd.high],
    },
    weights: { ...values.weights },
    fixed_targets: { ...values.fixed_targets },
    ga_config: { ...values.ga },
  };
}
