from __future__ import annotations

from app.db.models.job import JobModel
from app.db.repositories import JobRepository


def _job(status: str) -> JobModel:
    job = JobModel()
    job.status = status
    job.cancel_requested = False
    return job


def test_allowed_job_transitions():
    repo = JobRepository(session=None)  # type: ignore[arg-type]
    job = _job("queued")

    assert repo.mark_running(job, worker_id="worker-1") is True
    assert job.status == "running"
    assert job.worker_id == "worker-1"
    assert job.started_at is not None

    assert repo.mark_succeeded(job, progress={"generation": 2}) is True
    assert job.status == "succeeded"
    assert job.progress == {"generation": 2}
    assert job.finished_at is not None


def test_forbidden_job_transitions_are_rejected():
    repo = JobRepository(session=None)  # type: ignore[arg-type]
    queued = _job("queued")

    assert repo.mark_succeeded(queued) is False
    assert queued.status == "queued"

    terminal = _job("succeeded")
    assert repo.mark_running(terminal) is False
    assert repo.mark_failed(terminal) is False
    assert repo.mark_cancelled(terminal) is False
    assert terminal.status == "succeeded"


def test_terminal_states_are_immutable_and_cancel_is_guarded():
    repo = JobRepository(session=None)  # type: ignore[arg-type]
    job = _job("running")

    assert repo.mark_cancelled(job) is True
    assert job.status == "cancelled"
    assert repo.request_cancel(job) is False
    assert repo.mark_running(job) is False
    assert job.status == "cancelled"
