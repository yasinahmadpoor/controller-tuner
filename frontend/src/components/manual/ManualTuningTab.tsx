import { useEffect, useMemo, useState } from "react";

import { useSchema, useSimulate } from "../../hooks/queries";
import { getErrorMessage } from "../../lib/errors";
import type {
  ControllerType,
  SimulateResult,
  SystemSummary,
} from "../../types/api";
import { ErrorBanner } from "../common/ErrorBanner";
import { LoadingSpinner } from "../common/LoadingSpinner";
import { useToast } from "../common/ToastHost";
import { ManualResults } from "../results/ManualResults";

const CONTROLLERS: ControllerType[] = ["PID", "PI", "PD", "P", "FSF"];

interface AdvancedSettings {
  dt: number;
  max_time: number;
  target: number;
  min_control: number;
  max_control: number;
  input_channel: number;
  output_channel: number;
  seed: string;
}

function parseList(value: string): number[] | null {
  if (!value.trim()) {
    return null;
  }
  const parts = value.split(",").map((part) => Number(part.trim()));
  if (parts.some((part) => !Number.isFinite(part))) {
    return null;
  }
  return parts;
}

export function ManualTuningTab({
  system,
  result,
  onResult,
}: {
  system: SystemSummary;
  result: SimulateResult | null;
  onResult: (result: SimulateResult) => void;
}) {
  const [controllerType, setControllerType] = useState<ControllerType>("PID");
  const [gainsByController, setGainsByController] = useState<
    Partial<Record<ControllerType, Record<string, number>>>
  >({});
  const [initialState, setInitialState] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);
  const [advanced, setAdvanced] = useState<AdvancedSettings>({
    dt: system.simulation.dt,
    max_time: system.simulation.max_time,
    target: system.simulation.target,
    min_control: system.simulation.min_control,
    max_control: system.simulation.max_control,
    input_channel: system.simulation.input_channel,
    output_channel: system.simulation.output_channel,
    seed: "",
  });

  const schema = useSchema(system.system_id, controllerType);
  const simulation = useSimulate(system.system_id);
  const { pushToast } = useToast();

  useEffect(() => {
    if (!schema.data) {
      return;
    }
    setGainsByController((current) => {
      if (current[controllerType]) {
        return current;
      }
      const initial = Object.fromEntries(
        Object.entries(schema.data.params).map(([name, bounds]) => [
          name,
          Number(((bounds.min + bounds.max) / 2).toFixed(4)),
        ]),
      );
      return { ...current, [controllerType]: initial };
    });
  }, [controllerType, schema.data]);

  const gains = gainsByController[controllerType] ?? {};
  const params = schema.data?.params ?? {};
  const isLoadingSchema = schema.isPending;

  const initialList = useMemo(() => parseList(initialState), [initialState]);
  const initialError =
    initialState.trim().length > 0 && initialList === null
      ? "Use comma-separated finite numbers."
      : initialList !== null && initialList.length !== system.num_states
        ? `Expected ${system.num_states} values, received ${initialList.length}.`
        : null;

  function updateGain(name: string, value: number) {
    if (!Number.isFinite(value)) {
      return;
    }
    setGainsByController((current) => ({
      ...current,
      [controllerType]: {
        ...(current[controllerType] ?? {}),
        [name]: value,
      },
    }));
  }

  async function submit() {
    setValidationError(null);
    if (initialError) {
      setValidationError(initialError);
      return;
    }
    const boundsError = Object.entries(params).find(([name, bounds]) => {
      const value = gains[name];
      return value === undefined || value < bounds.min || value > bounds.max;
    });
    if (boundsError) {
      const [name, bounds] = boundsError;
      setValidationError(
        `${name} must be between ${bounds.min} and ${bounds.max}.`,
      );
      return;
    }
    try {
      const next = await simulation.mutateAsync({
        controller_type: controllerType,
        params: { ...gains },
        initial_state: initialList,
        seed: advanced.seed.trim() ? Number(advanced.seed) : null,
        overrides: {
          dt: advanced.dt,
          max_time: advanced.max_time,
          target: advanced.target,
          min_control: advanced.min_control,
          max_control: advanced.max_control,
          input_channel: advanced.input_channel,
          output_channel: advanced.output_channel,
        },
      });
      onResult(next);
      pushToast("Simulation saved to history", "success");
    } catch {
      // Rendered by the error banner below.
    }
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,420px)_minmax(0,1fr)]">
      <section className="card p-5 sm:p-6">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-bold text-slate-900">Manual tuning</h2>
            <p className="mt-1 text-sm text-slate-500">
              Choose a controller, tune the gains, and run a deterministic simulation.
            </p>
          </div>
          {isLoadingSchema ? <LoadingSpinner label="Schema" /> : null}
        </div>

        <label className="mt-5 block">
          <span className="label">Controller type</span>
          <select
            aria-label="Controller type"
            value={controllerType}
            onChange={(event) => {
              setControllerType(event.target.value as ControllerType);
              setValidationError(null);
            }}
            className="input mt-1"
          >
            {CONTROLLERS.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
        </label>

        {schema.isError ? (
          <div className="mt-4">
            <ErrorBanner
              title="Could not load gain schema"
              message={getErrorMessage(schema.error)}
              onDismiss={() => void schema.refetch()}
            />
          </div>
        ) : null}

        <div className="mt-5 space-y-4">
          {Object.entries(params).map(([name, bounds]) => {
            const value = gains[name] ?? bounds.min;
            return (
              <div key={name}>
                <div className="flex items-center justify-between gap-3">
                  <label htmlFor={`gain-${name}`} className="text-sm font-semibold text-slate-800">
                    {name}
                  </label>
                  <input
                    aria-label={`${name} value`}
                    type="number"
                    step="any"
                    min={bounds.min}
                    max={bounds.max}
                    value={value}
                    onChange={(event) => updateGain(name, Number(event.target.value))}
                    className="w-28 rounded-lg border border-slate-300 px-2 py-1 text-right text-sm"
                  />
                </div>
                <input
                  id={`gain-${name}`}
                  aria-label={`${name} slider`}
                  type="range"
                  min={bounds.min}
                  max={bounds.max}
                  step={(bounds.max - bounds.min) / 100}
                  value={value}
                  onChange={(event) => updateGain(name, Number(event.target.value))}
                  className="mt-2 w-full accent-accent-600"
                />
                <div className="flex justify-between text-[11px] text-slate-400">
                  <span>{bounds.min}</span>
                  <span>{bounds.max}</span>
                </div>
              </div>
            );
          })}
        </div>

        <details className="mt-5 rounded-xl border border-slate-200 bg-slate-50 p-4">
          <summary className="cursor-pointer text-sm font-semibold text-slate-700">
            Advanced simulation settings
          </summary>
          <div className="mt-4 grid grid-cols-2 gap-3">
            {(
              [
                ["dt", "dt"],
                ["max_time", "Max time"],
                ["target", "Target"],
                ["min_control", "Min control"],
                ["max_control", "Max control"],
                ["input_channel", "Input channel"],
                ["output_channel", "Output channel"],
              ] as const
            ).map(([key, label]) => (
              <label key={key} className="block">
                <span className="label">{label}</span>
                <input
                  type="number"
                  step="any"
                  className="input mt-1"
                  value={advanced[key]}
                  onChange={(event) =>
                    setAdvanced((current) => ({
                      ...current,
                      [key]: Number(event.target.value),
                    }))
                  }
                />
              </label>
            ))}
            <label className="block">
              <span className="label">Seed (optional)</span>
              <input
                type="number"
                className="input mt-1"
                value={advanced.seed}
                onChange={(event) =>
                  setAdvanced((current) => ({ ...current, seed: event.target.value }))
                }
              />
            </label>
          </div>
        </details>

        <label className="mt-5 block">
          <span className="label">Initial state (optional)</span>
          <input
            aria-label="Initial state"
            className="input mt-1"
            value={initialState}
            onChange={(event) => setInitialState(event.target.value)}
            placeholder={`e.g. ${Array.from({ length: system.num_states }, () => "0").join(", ")}`}
          />
          <span className="mt-1 block text-xs text-slate-500">
            Provide {system.num_states} comma-separated values or leave blank for the engine default.
          </span>
        </label>
        {initialError ? (
          <p className="mt-2 text-sm font-medium text-rose-700">{initialError}</p>
        ) : null}

        {(validationError || simulation.isError) ? (
          <div className="mt-4">
            <ErrorBanner
              title="Simulation not started"
              message={validationError ?? getErrorMessage(simulation.error)}
              onDismiss={() => {
                setValidationError(null);
                simulation.reset();
              }}
            />
          </div>
        ) : null}

        <button
          type="button"
          onClick={() => void submit()}
          disabled={simulation.isPending || isLoadingSchema}
          className="btn-primary mt-5 w-full"
        >
          {simulation.isPending ? (
            <>
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />
              Running simulation…
            </>
          ) : (
            "Run simulation"
          )}
        </button>
      </section>

      <section className="min-w-0">
        {result ? (
          <ManualResults result={result} target={advanced.target} />
        ) : (
          <div className="card grid min-h-[420px] place-items-center p-8 text-center">
            <div>
              <p className="text-lg font-bold text-slate-800">No simulation yet</p>
              <p className="mt-2 max-w-sm text-sm text-slate-500">
                Adjust the gains on the left and run a simulation to see the response,
                control input, stability, and metrics here.
              </p>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
