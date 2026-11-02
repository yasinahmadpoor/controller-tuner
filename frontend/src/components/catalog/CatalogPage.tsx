import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { createSystemFromCatalog } from "../../api/client";
import { useCatalog, useSystems } from "../../hooks/queries";
import { getErrorMessage } from "../../lib/errors";
import { formatDate } from "../../lib/format";
import type { CatalogEntry, SystemSummary } from "../../types/api";
import { EmptyState } from "../common/EmptyState";
import { ErrorBanner } from "../common/ErrorBanner";
import { LoadingSpinner } from "../common/LoadingSpinner";
import { useToast } from "../common/ToastHost";
import { UploadSystemDialog } from "./UploadSystemDialog";
import { WorkspacePickerDialog } from "./WorkspacePickerDialog";

function workspaceActionLabel(count: number): string {
  if (count === 0) return "Create workspace";
  if (count === 1) return "Open workspace";
  return `Choose workspace (${count})`;
}

function CaseStudyCard({
  entry,
  workspaceCount,
  onOpen,
  busy,
}: {
  entry: CatalogEntry;
  workspaceCount: number;
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
      <p className="mt-3 text-xs text-slate-500">
        {workspaceCount === 0
          ? "No workspace yet."
          : `${workspaceCount} existing workspace${workspaceCount === 1 ? "" : "s"} with saved history.`}
      </p>
      <div className="mt-4 flex flex-1 items-end">
        <button type="button" onClick={onOpen} disabled={busy} className="btn-primary w-full">
          {busy ? "Opening…" : workspaceActionLabel(workspaceCount)}
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
  const systems = useSystems({ limit: 100 });
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { pushToast } = useToast();
  const [uploadOpen, setUploadOpen] = useState(false);
  const [openingId, setOpeningId] = useState<string | null>(null);
  const [pickerEntry, setPickerEntry] = useState<CatalogEntry | null>(null);

  const create = useMutation({
    mutationFn: createSystemFromCatalog,
    onSuccess: (system) => {
      void queryClient.invalidateQueries({ queryKey: ["systems"] });
      pushToast(`Created ${system.name} workspace`, "success");
      setPickerEntry(null);
      navigate(`/systems/${system.system_id}/manual`);
    },
    onSettled: () => setOpeningId(null),
  });

  function workspacesFor(catalogId: string): SystemSummary[] {
    return (systems.data?.items ?? []).filter(
      (system) =>
        system.source_type === "catalog_json" && system.source_ref === catalogId,
    );
  }

  function openEntry(entry: CatalogEntry) {
    const matches = workspacesFor(entry.catalog_id);
    if (matches.length === 0) {
      setOpeningId(entry.catalog_id);
      create.mutate(entry.catalog_id);
      return;
    }
    if (matches.length === 1) {
      navigate(`/systems/${matches[0].system_id}/manual`);
      return;
    }
    setPickerEntry(entry);
  }

  function createNewFromPicker() {
    if (pickerEntry === null) return;
    setOpeningId(pickerEntry.catalog_id);
    create.mutate(pickerEntry.catalog_id);
  }

  const recentWorkspaces = (systems.data?.items ?? []).slice(0, 10);
  const pickerWorkspaces = pickerEntry ? workspacesFor(pickerEntry.catalog_id) : [];

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
            persisted in the workspace you choose.
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

      {catalog.isPending || systems.isPending ? <CatalogSkeleton /> : null}

      {catalog.isError ? (
        <ErrorBanner
          title="Catalog unavailable"
          message={getErrorMessage(catalog.error)}
          onDismiss={() => void catalog.refetch()}
        />
      ) : null}

      {systems.isError ? (
        <ErrorBanner
          title="Workspaces unavailable"
          message={getErrorMessage(systems.error)}
          onDismiss={() => void systems.refetch()}
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
              workspaceCount={workspacesFor(entry.catalog_id).length}
              busy={openingId === entry.catalog_id}
              onOpen={() => openEntry(entry)}
            />
          ))}
        </div>
      ) : null}

      {catalog.isFetching && !catalog.isPending ? (
        <div className="flex justify-end">
          <LoadingSpinner label="Refreshing catalog" />
        </div>
      ) : null}

      {systems.isSuccess && recentWorkspaces.length > 0 ? (
        <section className="card p-5 sm:p-6">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 className="text-lg font-bold text-slate-900">Recent workspaces</h2>
              <p className="mt-1 text-sm text-slate-500">
                Open an existing workspace directly to continue its saved history.
              </p>
            </div>
            <span className="text-xs font-semibold text-slate-500">
              {systems.data.total} total
            </span>
          </div>
          <ul className="mt-4 divide-y divide-slate-100">
            {recentWorkspaces.map((workspace) => (
              <li
                key={workspace.system_id}
                className="flex flex-wrap items-center justify-between gap-3 py-3"
              >
                <div>
                  <p className="text-sm font-semibold text-slate-900">{workspace.name}</p>
                  <p className="mt-0.5 text-xs text-slate-500">
                    {workspace.source_ref ?? workspace.source_type} ·{" "}
                    {formatDate(workspace.created_at)}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => navigate(`/systems/${workspace.system_id}/manual`)}
                  className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                >
                  Open
                </button>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {uploadOpen ? (
        <UploadSystemDialog
          onClose={() => setUploadOpen(false)}
          onCreated={(systemId) => navigate(`/systems/${systemId}/manual`)}
        />
      ) : null}

      {pickerEntry ? (
        <WorkspacePickerDialog
          entry={pickerEntry}
          workspaces={pickerWorkspaces}
          busy={openingId === pickerEntry.catalog_id}
          onOpen={(workspace) => navigate(`/systems/${workspace.system_id}/manual`)}
          onCreate={createNewFromPicker}
          onClose={() => setPickerEntry(null)}
        />
      ) : null}


    </div>
  );
}
