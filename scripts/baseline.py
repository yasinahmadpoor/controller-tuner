#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.engines.loader import load_engines  # noqa: E402
from tests.golden_utils import (  # noqa: E402
    GOLDEN_DIR,
    build_ga_golden,
    build_manual_golden,
    dump_json,
)


def main() -> int:
    load_engines(
        ga_repo=REPO_ROOT / "engines" / "gaTunerPID",
        manual_repo=REPO_ROOT / "engines" / "tunerPID",
    )

    dump_json(GOLDEN_DIR / "manual_ballbeam_pid.json", build_manual_golden())
    dump_json(GOLDEN_DIR / "ga_ballbeam_p5_g2_s42.json", build_ga_golden())

    print(f"Wrote golden fixtures to {GOLDEN_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
