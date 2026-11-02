import { zodResolver } from "@hookform/resolvers/zod";
import { useForm, type UseFormRegisterReturn } from "react-hook-form";

import { useOptimize } from "../../hooks/queries";
import { getErrorMessage } from "../../lib/errors";
import { formatMetric, metricLabel } from "../../lib/format";
import {
  GAIN_NAMES,
  OPTIMIZATION_METRICS,
  defaultsFromSystem,
  optimizationFormSchema,
  toOptimizeRequest,
  type OptimizationFormValues,
} from "../../lib/optimizationForm";
import type { OptimizeResult, SystemSummary } from "../../types/api";
import { ErrorBanner } from "../common/ErrorBanner";
import { useToast } from "../common/ToastHost";

function NumberInput({
  label,
  registration,
  error,
  step = "any",
}: {
  label: string;
  registration: UseFormRegisterReturn;
  error?: string;
  step?: string;
}) {
  return (
    <label className="block">
      <span className="label">{label}</span>
      <input
        aria-label={label}
        type="number"
        step={step}
        className="input mt-1"
        {...registration}
      />
      {error ? <span className="mt-1 block text-xs font-medium text-rose-700">{error}</span> : null}
    </label>
  );
}

export function AutoTuneForm({
  system,
  onOptimized,
}: {
  system: SystemSummary;
  onOptimized: (
    result: OptimizeResult,
    targets: OptimizationFormValues["fixed_targets"],
  ) => void;
}) {
  const defaults = defaultsFromSystem(system);
  const optimize = useOptimize(system.system_id);
  const { pushToast } = useToast();
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<OptimizationFormValues>({
    resolver: zodResolver(optimizationFormSchema),
    defaultValues: defaults,
    mode: "onTouched",
  });

  async function submit(values: OptimizationFormValues) {
    try {
      const result = await optimize.mutateAsync(toOptimizeRequest(values));
      onOptimized(result, values.fixed_targets);
      pushToast("Optimization saved to history", "success");
    } catch {
      // Rendered by the error banner below.
    }
  }

  return (
    <form
      className="card p-5 sm:p-6"
      onSubmit={handleSubmit(submit)}
      noValidate
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-slate-900">Auto-tune</h2>
          <p className="mt-1 max-w-2xl text-sm text-slate-500">
            Configure the GA search space, objective weights, and fixed targets. Defaults
            come from this system&apos;s case study.
          </p>
        </div>
        <button
          type="button"
          onClick={() => reset(defaults)}
          className="btn-secondary"
        >
          Reset to defaults
        </button>
      </div>

      <fieldset className="mt-6">
        <legend className="text-sm font-bold text-slate-900">Parameter ranges</legend>
        <div className="mt-3 grid gap-3 sm:grid-cols-3">
          {GAIN_NAMES.map((name) => (
            <div key={name} className="rounded-xl border border-slate-200 bg-slate-50 p-3">
              <p className="text-sm font-bold text-slate-800">{name}</p>
              <div className="mt-2 grid grid-cols-2 gap-2">
                <NumberInput
                  label={`${name} low`}
                  registration={register(`ranges.${name}.low`, { valueAsNumber: true })}
                  error={errors.ranges?.[name]?.low?.message}
                />
                <NumberInput
                  label={`${name} high`}
                  registration={register(`ranges.${name}.high`, { valueAsNumber: true })}
                  error={errors.ranges?.[name]?.high?.message}
                />
              </div>
            </div>
          ))}
        </div>
      </fieldset>

      <fieldset className="mt-6">
        <legend className="text-sm font-bold text-slate-900">Targets and weights</legend>
        <p className="mt-1 text-xs text-slate-500">
          Lower is better for all controlled metrics. A target is marked as hit when the
          achieved value is at or below it.
        </p>
        <div className="mt-3 space-y-3">
          {OPTIMIZATION_METRICS.map((metric) => (
            <div
              key={metric}
              className="grid items-start gap-3 rounded-xl border border-slate-200 p-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,180px)_minmax(0,180px)]"
            >
              <div>
                <p className="text-sm font-semibold text-slate-800">
                  {metricLabel(metric)}
                </p>
                <p className="mt-0.5 font-mono text-xs text-slate-400">{metric}</p>
              </div>
              <NumberInput
                label={`${metric} weight`}
                registration={register(`weights.${metric}`, { valueAsNumber: true })}
                error={errors.weights?.[metric]?.message}
              />
              <NumberInput
                label={`${metric} target`}
                registration={register(`fixed_targets.${metric}`, { valueAsNumber: true })}
                error={errors.fixed_targets?.[metric]?.message}
              />
            </div>
          ))}
        </div>
      </fieldset>

      <fieldset className="mt-6">
        <legend className="text-sm font-bold text-slate-900">GA settings</legend>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <NumberInput
            label="Population"
            step="1"
            registration={register("ga.population_size", { valueAsNumber: true })}
            error={errors.ga?.population_size?.message}
          />
          <NumberInput
            label="Generations"
            step="1"
            registration={register("ga.generations", { valueAsNumber: true })}
            error={errors.ga?.generations?.message}
          />
          <NumberInput
            label="Seed"
            step="1"
            registration={register("ga.seed", {
              setValueAs: (value: string) => (value === "" ? null : Number(value)),
            })}
            error={errors.ga?.seed?.message}
          />
          <NumberInput
            label="Max wall clock"
            registration={register("ga.max_wall_clock", { valueAsNumber: true })}
            error={errors.ga?.max_wall_clock?.message}
          />
        </div>
      </fieldset>

      {optimize.isError ? (
        <div className="mt-5">
          <ErrorBanner
            title="Optimization failed"
            message={getErrorMessage(optimize.error)}
            onDismiss={() => optimize.reset()}
          />
        </div>
      ) : null}

      <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs text-slate-500">
          Current target MSE:{" "}
          <span className="font-semibold">{formatMetric(defaults.fixed_targets.mse)}</span>
        </p>
        <button
          type="submit"
          disabled={optimize.isPending || isSubmitting}
          className="btn-primary min-w-40"
        >
          {optimize.isPending || isSubmitting ? (
            <>
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />
              Optimizing…
            </>
          ) : (
            "Run optimization"
          )}
        </button>
      </div>
    </form>
  );
}
