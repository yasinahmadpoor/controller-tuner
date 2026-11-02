#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = REPO_ROOT / "scripts" / "engine_sources.sha256"

TRACKED_PATHS: tuple[tuple[str, str], ...] = (
    ("engines/gaTunerPID/src", "*.py"),
    ("engines/gaTunerPID/app.py", ""),
    ("engines/gaTunerPID/case_studies/json", "*.json"),
    ("engines/tunerPID/src", "*.py"),
    ("engines/tunerPID/streamlit/app.py", ""),
    ("engines/tunerPID/case_studies", "*.py"),
)


def _tracked_files() -> list[Path]:
    files: list[Path] = []
    for relative, pattern in TRACKED_PATHS:
        path = REPO_ROOT / relative
        if not path.exists():
            continue
        if path.is_file():
            files.append(path)
            continue
        files.extend(
            candidate
            for candidate in path.rglob(pattern)
            if candidate.is_file()
            and "__pycache__" not in candidate.parts
            and candidate.suffix != ".pyc"
        )
    return sorted(set(files), key=lambda item: item.relative_to(REPO_ROOT).as_posix())


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def current_manifest() -> dict[str, str]:
    return {path.relative_to(REPO_ROOT).as_posix(): _hash_file(path) for path in _tracked_files()}


def read_manifest() -> dict[str, str]:
    if not MANIFEST.is_file():
        return {}
    entries: dict[str, str] = {}
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, relative = line.split("  ", 1)
        entries[relative] = digest
    return entries


def write_manifest(entries: dict[str, str]) -> None:
    MANIFEST.write_text(
        "".join(f"{digest}  {relative}\n" for relative, digest in sorted(entries.items())),
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify or update hashes of the read-only engine sources."
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Rewrite the manifest from the current engine files.",
    )
    args = parser.parse_args(argv)

    current = current_manifest()
    if args.write:
        write_manifest(current)
        print(f"Wrote {len(current)} entries to {MANIFEST}")
        return 0

    expected = read_manifest()
    if not expected:
        print(f"Manifest missing or empty: {MANIFEST}", file=sys.stderr)
        return 1

    missing = sorted(set(expected) - set(current))
    added = sorted(set(current) - set(expected))
    changed = sorted(
        relative
        for relative in set(current) & set(expected)
        if current[relative] != expected[relative]
    )

    if not (missing or added or changed):
        print(f"Engine sources unchanged ({len(current)} files).")
        return 0

    for label, paths in (
        ("Missing", missing),
        ("Added", added),
        ("Changed", changed),
    ):
        for relative in paths:
            print(f"{label}: {relative}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
