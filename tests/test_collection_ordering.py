import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_backend_tests_collected_before_e2e_tests():
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=PROJECT_ROOT,
    )
    assert result.returncode == 0, (
        f"pytest --collect-only failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )

    nodeids = [
        line.strip().replace("\\", "/")
        for line in result.stdout.splitlines()
        if "::" in line
    ]
    assert nodeids, f"No tests collected:\n{result.stdout}"

    first_e2e_index = next(
        (i for i, n in enumerate(nodeids) if n.startswith("tests/e2e/")),
        None,
    )
    last_backend_index = next(
        (
            i
            for i in range(len(nodeids) - 1, -1, -1)
            if not nodeids[i].startswith("tests/e2e/")
        ),
        None,
    )

    assert first_e2e_index is not None, f"No e2e tests collected: {nodeids[:5]}"
    assert last_backend_index is not None, f"No backend tests collected: {nodeids[:5]}"
    assert last_backend_index < first_e2e_index, (
        f"All backend tests must be collected before any e2e test, but a backend test "
        f"appears at index {last_backend_index} after an e2e test at index {first_e2e_index}.\n"
        f"First 10 ids: {nodeids[:10]}\n"
        f"Around the boundary: {nodeids[max(0, first_e2e_index - 2):first_e2e_index + 3]}"
    )
