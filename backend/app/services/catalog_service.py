"""Discovery and merge of curated case studies from both engine repositories.

Sources:
- ``gaTunerPID/case_studies/json/*.json`` (JSON metadata + embedded code)
- ``tunerPID/case_studies/*.py`` (standalone Python dynamics)

Entries are merged by slug; JSON metadata is authoritative for controls,
targets, trim values and fixed targets. Missing sources are skipped with a
logged warning, never crash the endpoint.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_JSON_DIR = Path("gaTunerPID/case_studies/json")
_PY_DIR = Path("tunerPID/case_studies")


def _slugify(stem: str) -> str:
    if "_" in stem:
        return stem.lower()
    snake = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", stem)
    snake = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", snake)
    return snake.lower()


@dataclass(frozen=True)
class CatalogEntry:
    catalog_id: str
    name: str
    description: str | None
    objective: str | None
    num_states: int
    num_inputs: int
    target: float
    capabilities: list[str]
    sources: dict[str, str]
    json_path: Path | None = None
    py_path: Path | None = None
    json_profile: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "catalog_id": self.catalog_id,
            "name": self.name,
            "description": self.description,
            "objective": self.objective,
            "num_states": self.num_states,
            "num_inputs": self.num_inputs,
            "target": self.target,
            "capabilities": list(self.capabilities),
            "sources": dict(self.sources),
        }


@dataclass
class Catalog:
    entries: dict[str, CatalogEntry] = field(default_factory=dict)


def load_catalog(repo_root: Path) -> Catalog:
    """Discover and merge case-study sources into curated entries by slug."""
    catalog = Catalog()
    json_entries: dict[str, dict[str, Any]] = {}
    json_paths: dict[str, Path] = {}
    if (_json_dir_abs := repo_root / _JSON_DIR).is_dir():
        for json_file in sorted(_json_dir_abs.glob("*.json")):
            try:
                profile = json.loads(json_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                logger.warning("skipping malformed case study %s: %s", json_file, exc)
                continue
            slug = _slugify(json_file.stem)
            json_entries[slug] = profile
            json_paths[slug] = json_file

    py_files = _py_case_studies(repo_root / _PY_DIR)

    all_slugs = sorted(set(json_entries) | set(py_files))
    for slug in all_slugs:
        profile = json_entries.get(slug)
        py_path = py_files.get(slug)
        if profile is None:
            logger.warning("case study %s has no JSON profile; skipped", slug)
            continue
        sources: dict[str, str] = {}
        if slug in json_paths:
            sources["json"] = _relative(json_paths[slug], repo_root)
        if py_path is not None:
            sources["python"] = _relative(py_path, repo_root)
        entry = CatalogEntry(
            catalog_id=slug,
            name=str(profile.get("system_name", slug)),
            description=profile.get("system_description"),
            objective=profile.get("control_objective"),
            num_states=int(profile["num_states"]),
            num_inputs=int(profile["num_inputs"]),
            target=float(profile["target"]),
            capabilities=["simulate", "optimize"],
            sources=sources,
            json_path=json_paths.get(slug),
            py_path=py_path,
            json_profile=profile,
        )
        catalog.entries[slug] = entry
    return catalog


def _py_case_studies(py_dir: Path) -> dict[str, Path]:
    if not py_dir.is_dir():
        return {}
    return {_slugify(file.stem): file for file in sorted(py_dir.glob("*.py")) if file.is_file()}


def _relative(path: Path, repo_root: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)


class CatalogService:
    """Serves the in-memory merged catalog and its entries."""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self._catalog = load_catalog(repo_root)

    def list_entries(self) -> list[CatalogEntry]:
        return list(self._catalog.entries.values())

    def get(self, catalog_id: str) -> CatalogEntry | None:
        return self._catalog.entries.get(catalog_id)

    def read_json_profile(self, entry: CatalogEntry) -> dict[str, Any] | None:
        """Return the merged JSON profile for an entry (authoritative metadata)."""
        if entry.json_profile is not None:
            return entry.json_profile
        return None

    def read_code(self, entry: CatalogEntry) -> str | None:
        """Return the canonical Python source for an entry.

        The embedded ``python_code`` from the JSON profile wins; otherwise the
        ``.py`` case study file is used.
        """
        profile = entry.json_profile
        if profile and profile.get("python_code"):
            return str(profile["python_code"])
        if entry.py_path is not None and entry.py_path.is_file():
            return entry.py_path.read_text(encoding="utf-8")
        return None
