import { useEffect, useState } from "react";
import { Navigate, useParams } from "react-router-dom";

import { useSystem } from "../../hooks/queries";
import type { SimulateResult } from "../../types/api";
import { ErrorBanner } from "../common/ErrorBanner";
import { LoadingSpinner } from "../common/LoadingSpinner";
import { AutoTuneTab } from "../auto/AutoTuneTab";
import { HistoryTab } from "../history/HistoryTab";
import { ManualTuningTab } from "../manual/ManualTuningTab";
import { SystemSummaryCard } from "./SystemSummaryCard";
import { WorkflowTabs } from "./WorkflowTabs";
import { getErrorMessage } from "../../lib/errors";
import { saveRunTrajectory } from "../../lib/runCache";

const VALID_TABS = ["manual", "auto", "history"] as const;
type Tab = (typeof VALID_TABS)[number];

function isTab(value: string | undefined): value is Tab {
  return value !== undefined && (VALID_TABS as readonly string[]).includes(value);
}

function storageKey(systemId: string) {
  return `controller-tuner:last-simulation:${systemId}`;
}

function readStoredResult(systemId: string): SimulateResult | null {
  try {
    const raw = window.sessionStorage.getItem(storageKey(systemId));
    return raw ? (JSON.parse(raw) as SimulateResult) : null;
  } catch {
    return null;
  }
}

export function WorkspacePage() {
  const { systemId, tab } = useParams<{ systemId: string; tab?: string }>();
  const system = useSystem(systemId);
  const [result, setResult] = useState<SimulateResult | null>(null);

  useEffect(() => {
    if (systemId) {
      setResult(readStoredResult(systemId));
    }
  }, [systemId]);

  if (!systemId) {
    return <Navigate to="/systems" replace />;
  }
  if (tab !== undefined && !isTab(tab)) {
    return <Navigate to={`/systems/${systemId}/manual`} replace />;
  }
  if (tab === undefined) {
    return <Navigate to={`/systems/${systemId}/manual`} replace />;
  }

  if (system.isPending) {
    return (
      <div className="flex justify-center py-20">
        <LoadingSpinner label="Loading system" />
      </div>
    );
  }
  if (system.isError) {
    return (
      <ErrorBanner
        title="Could not load system"
        message={getErrorMessage(system.error)}
        onDismiss={() => void system.refetch()}
      />
    );
  }

  function saveResult(next: SimulateResult) {
    setResult(next);
    window.sessionStorage.setItem(storageKey(systemId as string), JSON.stringify(next));
    saveRunTrajectory(next.run_id, {
      time_points: next.time_points,
      trajectory: next.trajectory,
      control_signals: next.control_signals,
    });
  }

  return (
    <div className="space-y-6">
      <SystemSummaryCard system={system.data} />
      <WorkflowTabs systemId={systemId} />
      {tab === "manual" ? (
        <ManualTuningTab
          key={system.data.system_id}
          system={system.data}
          result={result}
          onResult={saveResult}
        />
      ) : null}
      {tab === "auto" ? <AutoTuneTab key={system.data.system_id} system={system.data} /> : null}
      {tab === "history" ? <HistoryTab systemId={systemId} /> : null}
    </div>
  );
}
