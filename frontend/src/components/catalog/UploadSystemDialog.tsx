import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { useCreateSystem } from "../../hooks/queries";
import { getErrorMessage } from "../../lib/errors";
import { ErrorBanner } from "../common/ErrorBanner";
import { useToast } from "../common/ToastHost";

const uploadSchema = z
  .object({
    name: z.string().trim().min(1, "Name is required"),
    num_states: z.coerce.number().int().positive("Must be positive"),
    dt: z.coerce.number().positive("Must be greater than 0"),
    max_time: z.coerce.number().positive("Must be greater than 0"),
    target: z.coerce.number(),
    min_control: z.coerce.number(),
    max_control: z.coerce.number(),
    input_channel: z.coerce.number().int().min(0),
    output_channel: z.coerce.number().int().min(0),
    trim_values: z.string().min(1, "Provide at least one value"),
    trim_ics: z.string().min(1, "Provide one value per state"),
  })
  .refine((values) => values.min_control < values.max_control, {
    path: ["max_control"],
    message: "Max control must be greater than min control",
  });

type UploadValues = z.infer<typeof uploadSchema>;

const defaults: UploadValues = {
  name: "",
  num_states: 2,
  dt: 0.01,
  max_time: 10,
  target: 0,
  min_control: -10,
  max_control: 10,
  input_channel: 0,
  output_channel: 0,
  trim_values: "0",
  trim_ics: "0,0",
};

function parseList(value: string): number[] {
  return value
    .split(",")
    .map((part) => Number(part.trim()))
    .filter((part) => Number.isFinite(part));
}

export function UploadSystemDialog({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (systemId: string) => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const create = useCreateSystem();
  const { pushToast } = useToast();
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<UploadValues>({
    resolver: zodResolver(uploadSchema),
    defaultValues: defaults,
  });

  function acceptFile(candidate: File | null) {
    if (candidate === null) {
      setFile(null);
      return;
    }
    if (!candidate.name.toLowerCase().endsWith(".py")) {
      setFile(null);
      setFileError("Only .py files are supported.");
      return;
    }
    setFileError(null);
    setFile(candidate);
  }

  async function submit(values: UploadValues) {
    if (file === null) {
      setFileError("Choose a .py file before uploading.");
      return;
    }
    try {
      const system = await create.mutateAsync({
        file,
        metadata: {
          name: values.name,
          num_states: values.num_states,
          dt: values.dt,
          max_time: values.max_time,
          target: values.target,
          min_control: values.min_control,
          max_control: values.max_control,
          input_channel: values.input_channel,
          output_channel: values.output_channel,
          trim_values: parseList(values.trim_values),
          trim_ics: parseList(values.trim_ics),
        },
      });
      pushToast(`Uploaded ${system.name}`, "success");
      onCreated(system.system_id);
      onClose();
    } catch {
      // The mutation error is rendered below.
    }
  }

  return (
    <div className="fixed inset-0 z-40 flex items-start justify-center overflow-y-auto bg-slate-900/40 p-4 backdrop-blur-sm">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="upload-title"
        className="card my-6 w-full max-w-3xl p-6"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 id="upload-title" className="text-xl font-bold text-slate-900">
              Upload a system
            </h2>
            <p className="mt-1 text-sm text-slate-500">
              Upload Python dynamics and provide the metadata needed to simulate and optimize.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close upload dialog"
            className="rounded-lg px-2 py-1 text-xl text-slate-500 hover:bg-slate-100"
          >
            ×
          </button>
        </div>

        <form className="mt-6 space-y-5" onSubmit={handleSubmit(submit)} noValidate>
          <div
            onDragOver={(event) => {
              event.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(event) => {
              event.preventDefault();
              setDragging(false);
              acceptFile(event.dataTransfer.files.item(0));
            }}
            className={[
              "rounded-2xl border-2 border-dashed px-6 py-8 text-center transition",
              dragging ? "border-accent-500 bg-accent-50" : "border-slate-300 bg-slate-50",
            ].join(" ")}
          >
            <p className="text-sm font-semibold text-slate-800">
              Drag and drop a Python file here
            </p>
            <p className="mt-1 text-xs text-slate-500">Only .py files are accepted.</p>
            <label className="btn-secondary mt-4 cursor-pointer">
              Choose file
              <input
                type="file"
                accept=".py"
                className="sr-only"
                onChange={(event) => acceptFile(event.target.files?.item(0) ?? null)}
              />
            </label>
            {file ? (
              <p className="mt-3 text-sm font-medium text-emerald-700">{file.name}</p>
            ) : null}
            {fileError ? (
              <p role="alert" className="mt-3 text-sm font-medium text-rose-700">
                {fileError}
              </p>
            ) : null}
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block sm:col-span-2">
              <span className="label">Name</span>
              <input className="input mt-1" {...register("name")} />
              {errors.name ? <span className="text-xs text-rose-700">{errors.name.message}</span> : null}
            </label>
            <label className="block">
              <span className="label">States</span>
              <input type="number" className="input mt-1" {...register("num_states")} />
              {errors.num_states ? (
                <span className="text-xs text-rose-700">{errors.num_states.message}</span>
              ) : null}
            </label>
            <label className="block">
              <span className="label">Target</span>
              <input type="number" step="any" className="input mt-1" {...register("target")} />
            </label>
            <label className="block">
              <span className="label">dt</span>
              <input type="number" step="any" className="input mt-1" {...register("dt")} />
            </label>
            <label className="block">
              <span className="label">Max time</span>
              <input type="number" step="any" className="input mt-1" {...register("max_time")} />
            </label>
            <label className="block">
              <span className="label">Min control</span>
              <input type="number" step="any" className="input mt-1" {...register("min_control")} />
            </label>
            <label className="block">
              <span className="label">Max control</span>
              <input type="number" step="any" className="input mt-1" {...register("max_control")} />
              {errors.max_control ? (
                <span className="text-xs text-rose-700">{errors.max_control.message}</span>
              ) : null}
            </label>
            <label className="block">
              <span className="label">Input channel</span>
              <input type="number" className="input mt-1" {...register("input_channel")} />
            </label>
            <label className="block">
              <span className="label">Output channel</span>
              <input type="number" className="input mt-1" {...register("output_channel")} />
            </label>
            <label className="block">
              <span className="label">Trim values (comma separated)</span>
              <input className="input mt-1" {...register("trim_values")} />
            </label>
            <label className="block">
              <span className="label">Trim ICs (comma separated)</span>
              <input className="input mt-1" {...register("trim_ics")} />
            </label>
          </div>

          {create.isError ? (
            <ErrorBanner message={getErrorMessage(create.error)} onDismiss={() => create.reset()} />
          ) : null}

          <div className="flex justify-end gap-3">
            <button type="button" onClick={onClose} className="btn-secondary">
              Cancel
            </button>
            <button type="submit" disabled={isSubmitting || create.isPending} className="btn-primary">
              {create.isPending ? "Uploading…" : "Upload system"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
