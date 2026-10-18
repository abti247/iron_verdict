"""Stale browser cache after a deploy — a device that already had the app open
must load the new static files, not old ones from its HTTP cache.

Without an explicit ``Cache-Control`` a browser may reuse a cached file without
asking the server (heuristic freshness, typically 10 % of the file's age), so
new HTML ran with old JavaScript after a deploy (#135). The test serves a
temporary module under ``/static`` whose ``Last-Modified`` lies weeks in the
past, changes it on the server as a deploy would, and opens the app again.

In-process only: it writes into the server's static directory.
"""

import os
import time
from pathlib import Path

import pytest

import iron_verdict.main as main

PROBE_NAME = "_e2e_cache_probe.js"
THIRTY_DAYS_S = 30 * 24 * 3600

IMPORT_PROBE = f"async () => (await import('/static/{PROBE_NAME}')).VERSION"


@pytest.fixture()
def probe_file():
    path = Path(main.static_dir) / PROBE_NAME
    yield path
    path.unlink(missing_ok=True)


def _write(path, version, mtime=None):
    path.write_text(f"export const VERSION = '{version}';\n", encoding="utf-8")
    if mtime is not None:
        os.utime(path, (mtime, mtime))


def test_changed_static_file_is_loaded_after_redeploy(competition, server_url, probe_file):
    """Open the app and import a static module (old Last-Modified → v1) →
    the module changes on the server (v2) → the same device opens the app
    again (new document, warm HTTP cache) and imports the module → v2."""
    _write(probe_file, "v1", mtime=time.time() - THIRTY_DAYS_S)
    page = competition.new_context().new_page()
    page.goto(server_url)
    assert page.evaluate(IMPORT_PROBE) == "v1"

    _write(probe_file, "v2")
    page.goto(server_url)
    assert page.evaluate(IMPORT_PROBE) == "v2"
