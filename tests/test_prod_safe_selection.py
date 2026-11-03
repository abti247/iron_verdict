"""The ``prod_safe`` selection run by the production check of the release chain.

``production-check`` in ``.github/workflows/main.yml`` runs only ``prod_safe``
E2E tests against https://iron-verdict.com (rate limit 10 new sessions per
hour per IP). Every one of them must also be ``remote_safe``: the image check
proves on its PR that it runs against a deployed server, and staging runs it
again before the release, so no test runs against production for the first
time.
"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _collect(marker_expression):
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/e2e/", "--collect-only", "-q", "-m", marker_expression],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=PROJECT_ROOT,
    )
    # Exit code 5: no tests selected.
    assert result.returncode in (0, 5), f"collection failed:\n{result.stdout}\n{result.stderr}"
    return {line.strip().replace("\\", "/") for line in result.stdout.splitlines() if "::" in line}


def test_prod_safe_selects_smoke_and_competition_flow():
    files = {nodeid.split("::")[0] for nodeid in _collect("prod_safe")}
    assert files == {"tests/e2e/test_smoke.py", "tests/e2e/test_competition_flow.py"}


def test_every_prod_safe_test_is_remote_safe():
    assert _collect("prod_safe and not remote_safe") == set()
