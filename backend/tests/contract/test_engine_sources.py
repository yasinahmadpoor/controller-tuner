from __future__ import annotations

import subprocess
import sys

from tests.golden_utils import REPO_ROOT


def test_read_only_engine_sources_match_manifest():
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "verify_engines.py")],
        check=False,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
