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
