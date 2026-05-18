"""Smoke test — verify E2E infrastructure works."""

from playwright.sync_api import expect


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
