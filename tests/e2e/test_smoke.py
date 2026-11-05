"""Smoke tests — the app starts, serves its pages and assets, and accepts a judge.

Also the container smoke test: CI runs this file with ``E2E_BASE_URL``
against the freshly built Docker image (see ``.github/workflows/image.yml``),
so it must not depend on in-process server state. Like every ``remote_safe``
test it also runs against Railway staging before a release, and as
``prod_safe`` against production after the release deploy.
"""

import json
import os
import re

import httpx
from httpx_ws import connect_ws
import pytest
from playwright.sync_api import expect

pytestmark = [pytest.mark.remote_safe, pytest.mark.prod_safe]


def test_health_endpoint_reports_ok(server_url):
    response = httpx.get(f"{server_url}/health", timeout=5)
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_every_static_asset_the_app_loads_is_served(server_url):
    """Start from / and /vportal, follow every /static/... reference, every
    ES-module import and every CSS url(), and require each file to be served. Catches files missing
    from the image (.dockerignore, package data) before a deploy does."""
    pending = {"/static/locales/en.json", "/static/locales/de.json"}
    for path in ("/", "/vportal"):
        response = httpx.get(f"{server_url}{path}", timeout=5)
        assert response.status_code == 200
        pending.update(re.findall(r"""["'](/static/[^"'?#]+)""", response.text))

    served, missing = set(), []
    while pending:
        asset = pending.pop()
        served.add(asset)
        response = httpx.get(f"{server_url}{asset}", timeout=5)
        if response.status_code != 200:
            missing.append(asset)
            continue
        if asset.endswith(".js"):
            base = asset.rsplit("/", 1)[0]
            for rel in re.findall(r"""(?:from|import\()\s*["']\./([^"']+)["']""", response.text):
                if f"{base}/{rel}" not in served:
                    pending.add(f"{base}/{rel}")
        if asset.endswith(".css"):
            for ref in re.findall(r"""url\(\s*["']?(/static/[^"')?#]+)""", response.text):
                if ref not in served:
                    pending.add(ref)

    assert missing == []
    # The crawl must reach the app and the VPortal client, or it proves nothing.
    assert {"/static/js/app.js", "/static/js/vportalClient.js", "/static/js/vportalQueries.js"} <= served
    # ...and the self-hosted libraries and fonts the page needs without internet.
    assert {
        "/static/vendor/alpinejs-3.14.1.min.js",
        "/static/vendor/qrcodejs-1.0.0.min.js",
        "/static/fonts/bebas-neue-400-latin.woff2",
        "/static/fonts/rajdhani-700-latin.woff2",
    } <= served


def test_app_version_is_rendered(server_url):
    """The build injects APP_VERSION (sha-<commit> for CI images); the page must
    show it instead of the raw placeholder. E2E_EXPECTED_APP_VERSION pins it."""
    html = httpx.get(server_url, timeout=5).text
    assert "__APP_VERSION__" not in html
    expected = os.environ.get("E2E_EXPECTED_APP_VERSION")
    if expected:
        version = re.search(r'<div class="app-version">\s*(.*?)\s*</div>', html).group(1)
        assert version == expected


def test_websocket_join_as_head_judge(server_url, created_sessions):
    """Create a session over HTTP, open /ws (with the page's Origin, as a
    browser does) and join as head judge: the server answers with join_success
    and the session state."""
    with httpx.Client(base_url=server_url, timeout=5) as client:
        created = client.post("/api/sessions", json={"name": "Smoke WS"})
        assert created.status_code == 200
        code = created.json()["session_code"]
        created_sessions.append(code)

        # A browser always sends Origin; CI starts the image with
        # ALLOWED_ORIGIN set to this URL, so the origin check is exercised.
        with connect_ws(f"{server_url}/ws", client, headers={"Origin": server_url}) as ws:
            ws.send_text(json.dumps({"type": "join", "session_code": code, "role": "center_judge"}))
            reply = json.loads(ws.receive_text(timeout=5))

    assert reply["type"] == "join_success"
    assert reply["is_head"] is True
    assert reply["session_state"]["name"] == "Smoke WS"


def test_landing_page_loads(page, server_url):
    page.goto(server_url)
    expect(page.locator(".brand-iron").first).to_have_text("Iron Verdict")


def test_create_session_shows_role_select(page, server_url):
    page.goto(server_url)
    page.get_by_test_id("session-name-input").fill("Smoke Test")
    page.get_by_role("button", name="Create New Session").click()
    expect(page.locator(".role-wrap")).to_be_visible()
    expect(page.locator(".session-tag .code")).not_to_be_empty()


def test_vportal_session_shows_connect_button_on_role_select(page, server_url):
    page.goto(server_url + "/vportal")
    page.get_by_test_id("session-name-input").fill("VPortal Test")
    page.get_by_role("button", name="Create New Session").click()
    page.locator(".role-wrap").wait_for(state="visible")
    expect = __import__('playwright.sync_api', fromlist=['expect']).expect
    expect(page.locator(".vportal-connect-btn")).to_be_visible()


def test_generic_session_does_not_show_connect_button(page, server_url):
    page.goto(server_url + "/")
    page.get_by_test_id("session-name-input").fill("Generic Test")
    page.get_by_role("button", name="Create New Session").click()
    page.locator(".role-wrap").wait_for(state="visible")
    expect = __import__('playwright.sync_api', fromlist=['expect']).expect
    expect(page.locator(".vportal-connect-btn")).to_have_count(0)
