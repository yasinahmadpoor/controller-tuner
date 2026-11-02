import type { TrajectoryPayload } from "../types/api";

const PREFIX = "controller-tuner:trajectory:";

export function saveRunTrajectory(runId: string, payload: TrajectoryPayload): void {
  try {
    window.localStorage.setItem(PREFIX + runId, JSON.stringify(payload));
  } catch {
    // Large trajectories may exceed storage quota; the backend artifact remains canonical.
  }
}

export function readRunTrajectory(runId: string): TrajectoryPayload | null {
  try {
    const raw = window.localStorage.getItem(PREFIX + runId);
    return raw ? (JSON.parse(raw) as TrajectoryPayload) : null;
  } catch {
    return null;
  }
}
