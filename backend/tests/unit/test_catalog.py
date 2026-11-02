from __future__ import annotations

from pathlib import Path

from app.services.catalog_service import CatalogService


def test_catalog_discovers_and_merges_case_studies():
    repo_root = Path(__file__).resolve().parents[3]
    service = CatalogService(repo_root=repo_root)

    entries = {entry.catalog_id: entry for entry in service.list_entries()}
    assert set(entries) == {"ball_beam", "dc_motor", "inv_pendulum"}


def test_catalog_uses_json_metadata_and_exposes_sources():
    repo_root = Path(__file__).resolve().parents[3]
    service = CatalogService(repo_root=repo_root)

    entry = service.get("ball_beam")
    assert entry is not None
    assert entry.target == 0.0
    assert entry.num_states == 2
    assert entry.sources["json"].endswith("gaTunerPID/case_studies/json/BallBeam.json")
    assert entry.sources["python"].endswith("tunerPID/case_studies/BallBeam.py")
