"""Smoke tests — the app starts, serves its pages and assets, and accepts a judge.

Also the container smoke test: CI runs this file with ``E2E_BASE_URL``
against the freshly built Docker image (see ``.github/workflows/image.yml``),
so it must not depend on in-process server state. Keep it to a handful of
sessions: creating one is rate-limited per client IP (10/hour).
"""

import json
import os
import re

import httpx
from httpx_ws import connect_ws
from playwright.sync_api import expect


def test_health_endpoint_reports_ok(server_url):
    response = httpx.get(f"{server_url}/health", timeout=5)
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_every_static_asset_the_app_loads_is_served(server_url):
    """Start from / and /vportal, follow every /static/... reference and every
    ES-module import, and require each file to be served. Catches files missing
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

    assert missing == []
    # The crawl must reach the app and the VPortal client, or it proves nothing.
    assert {"/static/js/app.js", "/static/js/vportalClient.js", "/static/js/vportalQueries.js"} <= served


def test_app_version_is_rendered(server_url):
    """The build injects APP_VERSION (sha-<commit> for CI images); the page must
    show it instead of the raw placeholder. E2E_EXPECTED_APP_VERSION pins it."""
    html = httpx.get(server_url, timeout=5).text
    assert "__APP_VERSION__" not in html
    expected = os.environ.get("E2E_EXPECTED_APP_VERSION")
    if expected:
        version = re.search(r'<div class="app-version">\s*(.*?)\s*</div>', html).group(1)
        assert version == expected


def test_websocket_join_as_head_judge(server_url):
    """Create a session over HTTP, open /ws and join as head judge: the server
    answers with join_success and the session state."""
    with httpx.Client(base_url=server_url, timeout=5) as client:
        created = client.post("/api/sessions", json={"name": "Smoke WS"})
        assert created.status_code == 200
        code = created.json()["session_code"]

        with connect_ws(f"{server_url}/ws", client) as ws:
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
    page.locator('[x-model="newSessionName"]').fill("Smoke Test")
    page.get_by_role("button", name="Create New Session").click()
    expect(page.locator(".role-wrap")).to_be_visible()
    expect(page.locator(".session-tag .code")).not_to_be_empty()


def test_vportal_client_module_loads(page, server_url):
    page.goto(server_url + "/vportal")
    result = page.evaluate("""
        async () => {
            const m = await import('/static/js/vportalClient.js');
            return {
                hasLogin: typeof m.vportalClient.login === 'function',
                hasIsConnected: typeof m.vportalClient.isConnected === 'function',
                hasLogout: typeof m.vportalClient.logout === 'function',
            };
        }
    """)
    assert result == {"hasLogin": True, "hasIsConnected": True, "hasLogout": True}


def test_vportal_client_login_stores_token(page, server_url):
    page.goto(server_url + "/vportal")
    page.evaluate("""
        () => {
            // Stub fetch for the proxy login endpoint
            window.fetch = async (url, opts) => {
                if (url === '/api/vportal/login') {
                    return new Response(JSON.stringify({
                        access_token: 'jwt-test',
                        exp: 9999999999,
                        fetch_interval_ms: 3000,
                    }), { status: 200, headers: {'Content-Type': 'application/json'} });
                }
                return new Response('', { status: 404 });
            };
        }
    """)
    result = page.evaluate("""
        async () => {
            const m = await import('/static/js/vportalClient.js');
            await m.vportalClient.login('SESSION1', 'bvdk.vportal-online.de', 'u', 'p');
            const raw = localStorage.getItem('vportal:SESSION1');
            return JSON.parse(raw);
        }
    """)
    assert result["token"] == "jwt-test"
    assert result["host"] == "bvdk.vportal-online.de"
    assert result["fetch_interval_ms"] == 3000


def test_vportal_client_fetch_active_attempt_returns_normalized_shape(page, server_url):
    page.goto(server_url + "/vportal")
    page.evaluate("""
        () => {
            const responses = {
                '/api/vportal/login': {
                    access_token: 'jwt', exp: 9999999999, fetch_interval_ms: 3000,
                },
                'COMP_ID': { data: { profile: { competition: { id: 'C-1' } } } },
                'GROUP':   { data: { competitionGroupList: { competitionGroups: [{ id: 'G-1' }] } } },
                'ATHLETES': { data: { competitionAthleteAttemptList: { competitionAthleteAttempts: [{
                    id: 'A-1', attempt: 2, discipline: 'SQUAT', weight: 215, status: null,
                    competitionAthlete: {
                        firstName: 'Maria', lastName: 'Schneider',
                        club: { name: 'SV Eisenkraft Berlin' },
                        bodyWeightCategory: { name: '-72 kg' },
                        ageCategory: { name: 'Open' },
                    }
                }] } } }
            };
            window.fetch = async (url, opts) => {
                if (url === '/api/vportal/login') {
                    return new Response(JSON.stringify(responses['/api/vportal/login']), { status: 200 });
                }
                const body = JSON.parse(opts.body);
                let key = 'ATHLETES';
                if (body.query.includes('profile')) key = 'COMP_ID';
                else if (body.query.includes('competitionGroupList')) key = 'GROUP';
                return new Response(JSON.stringify(responses[key]), { status: 200 });
            };
        }
    """)
    result = page.evaluate("""
        async () => {
            const m = await import('/static/js/vportalClient.js');
            await m.vportalClient.login('S1', 'bvdk.vportal-online.de', 'u', 'p');
            m.vportalClient.setStage('S1', 'STAGE-1', 'Platform 1');
            return await m.vportalClient.fetchActiveAttempt('S1');
        }
    """)
    assert result["firstName"] == "Maria"
    assert result["lastName"] == "Schneider"
    assert result["club"] == "SV Eisenkraft Berlin"
    assert result["discipline"] == "SQUAT"
    assert result["attempt"] == 2
    assert result["weight"] == 215
    assert result["bodyWeightCategory"] == "-72 kg"
    assert result["ageCategory"] == "Open"


def test_vportal_client_poll_invokes_onerror_on_401(page, server_url):
    page.goto(server_url + "/vportal")
    page.evaluate("""
        () => {
            window.fetch = async (url) => {
                if (url === '/api/vportal/login') {
                    return new Response(JSON.stringify({
                        access_token: 'jwt', exp: 9999999999, fetch_interval_ms: 100,
                    }), { status: 200 });
                }
                if (url === '/api/vportal/graphql') {
                    return new Response('expired', { status: 401 });
                }
                return new Response('', { status: 404 });
            };
        }
    """)
    result = page.evaluate("""
        async () => {
            const m = await import('/static/js/vportalClient.js');
            await m.vportalClient.login('S1', 'bvdk.vportal-online.de', 'u', 'p');
            m.vportalClient.setStage('S1', 'STAGE-1', 'P1');
            return await new Promise((resolve) => {
                m.vportalClient.pollActiveAttempt('S1', 100, () => {}, (kind) => resolve(kind));
            });
        }
    """)
    assert result == "token-expired"


def test_vportal_session_shows_connect_button_on_role_select(page, server_url):
    page.goto(server_url + "/vportal")
    page.locator('[x-model="newSessionName"]').fill("VPortal Test")
    page.get_by_role("button", name="Create New Session").click()
    page.locator(".role-wrap").wait_for(state="visible")
    expect = __import__('playwright.sync_api', fromlist=['expect']).expect
    expect(page.locator(".vportal-connect-btn")).to_be_visible()


def test_generic_session_does_not_show_connect_button(page, server_url):
    page.goto(server_url + "/")
    page.locator('[x-model="newSessionName"]').fill("Generic Test")
    page.get_by_role("button", name="Create New Session").click()
    page.locator(".role-wrap").wait_for(state="visible")
    expect = __import__('playwright.sync_api', fromlist=['expect']).expect
    expect(page.locator(".vportal-connect-btn")).to_have_count(0)
