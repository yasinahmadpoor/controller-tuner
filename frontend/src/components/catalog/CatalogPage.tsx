import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { createSystemFromCatalog } from "../../api/client";
import { useCatalog } from "../../hooks/queries";
import { getErrorMessage } from "../../lib/errors";
import type { CatalogEntry } from "../../types/api";
import { EmptyState } from "../common/EmptyState";
import { ErrorBanner } from "../common/ErrorBanner";
import { LoadingSpinner } from "../common/LoadingSpinner";
import { useToast } from "../common/ToastHost";
import { UploadSystemDialog } from "./UploadSystemDialog";

function CaseStudyCard({
  entry,
  onOpen,
  busy,
}: {
  entry: CatalogEntry;
  onOpen: () => void;
  busy: boolean;
}) {
  return (
    <article className="card flex h-full flex-col p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-slate-900">{entry.name}</h2>
          <p className="mt-1 text-sm text-slate-500">
            {entry.description ?? "Curated control case study"}
          </p>
        </div>
        <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-600">
          {entry.catalog_id}
        </span>
      </div>
      <dl className="mt-4 grid grid-cols-3 gap-3 rounded-xl bg-slate-50 p-3 text-sm">
        <div>
          <dt className="label">States</dt>
          <dd className="mt-1 font-semibold text-slate-900">{entry.num_states}</dd>
        </div>
        <div>
          <dt className="label">Inputs</dt>
          <dd className="mt-1 font-semibold text-slate-900">{entry.num_inputs}</dd>
        </div>
        <div>
          <dt className="label">Target</dt>
          <dd className="mt-1 font-semibold text-slate-900">{entry.target}</dd>
        </div>
      </dl>
      <div className="mt-4 flex flex-wrap gap-2">
        {entry.capabilities.map((capability) => (
          <span
            key={capability}
            className="rounded-full bg-accent-50 px-2.5 py-1 text-xs font-semibold capitalize text-accent-700"
          >
            {capability}
          </span>
        ))}
      </div>
      <div className="mt-5 flex flex-1 items-end">
        <button type="button" onClick={onOpen} disabled={busy} className="btn-primary w-full">
          {busy ? "Opening…" : "Open workspace"}
        </button>
      </div>
    </article>
  );
}

function CatalogSkeleton() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3" aria-label="Loading systems">
      {[0, 1, 2].map((index) => (
        <div key={index} className="card animate-pulse p-5">
          <div className="h-5 w-1/2 rounded bg-slate-200" />
          <div className="mt-3 h-3 w-4/5 rounded bg-slate-100" />
          <div className="mt-6 h-20 rounded-xl bg-slate-100" />
          <div className="mt-5 h-10 rounded-xl bg-slate-100" />
        </div>
      ))}
    </div>
  );
}

export function CatalogPage() {
  const catalog = useCatalog();
  const navigate = useNavigate();
  const { pushToast } = useToast();
  const [uploadOpen, setUploadOpen] = useState(false);
  const [openingId, setOpeningId] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: createSystemFromCatalog,
    onSuccess: (system) => {
      pushToast(`Loaded ${system.name}`, "success");
      navigate(`/systems/${system.system_id}/manual`);
    },
    onSettled: () => setOpeningId(null),
  });

  return (
    <div className="space-y-8">
      <section className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="text-sm font-semibold uppercase tracking-widest text-accent-600">
            System catalog
          </p>
          <h1 className="mt-1 text-3xl font-black tracking-tight text-slate-900">
            Pick a plant to tune
          </h1>
          <p className="mt-2 max-w-2xl text-sm text-slate-600">
            Start from a curated case study or upload your own Python dynamics. Every run is
            persisted so you can reopen it later.
          </p>
        </div>
        <button type="button" onClick={() => setUploadOpen(true)} className="btn-primary">
          Upload system
        </button>
      </section>

      {create.isError ? (
        <ErrorBanner
          title="Could not open system"
          message={getErrorMessage(create.error)}
          onDismiss={() => create.reset()}
        />
      ) : null}

      {catalog.isPending ? <CatalogSkeleton /> : null}

      {catalog.isError ? (
        <ErrorBanner
          title="Catalog unavailable"
          message={getErrorMessage(catalog.error)}
          onDismiss={() => void catalog.refetch()}
        />
      ) : null}

      {catalog.isSuccess && catalog.data.items.length === 0 ? (
        <EmptyState title="No systems found">
          Upload a Python dynamics file to create the first system.
        </EmptyState>
      ) : null}

      {catalog.isSuccess && catalog.data.items.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {catalog.data.items.map((entry) => (
            <CaseStudyCard
              key={entry.catalog_id}
              entry={entry}
              busy={openingId === entry.catalog_id}
              onOpen={() => {
                setOpeningId(entry.catalog_id);
                create.mutate(entry.catalog_id);
              }}
            />
          ))}
        </div>
      ) : null}

      {catalog.isFetching && !catalog.isPending ? (
        <div className="flex justify-end">
          <LoadingSpinner label="Refreshing catalog" />
        </div>
      ) : null}

      {uploadOpen ? (
        <UploadSystemDialog
          onClose={() => setUploadOpen(false)}
          onCreated={(systemId) => navigate(`/systems/${systemId}/manual`)}
        />
      ) : null}
    </div>
  );
}
