#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.engines.loader import ga, load_engines, manual  # noqa: E402


def main() -> int:
    load_engines(
        ga_repo=REPO_ROOT / "gaTunerPID",
        manual_repo=REPO_ROOT / "tunerPID",
    )

    print("manual_engine:", ", ".join(sorted(manual())))
    print("src (GA):", ", ".join(sorted(ga())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
