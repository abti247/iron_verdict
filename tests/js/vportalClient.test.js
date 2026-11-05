import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { vportalClient } from '../../src/iron_verdict/static/js/vportalClient.js';

// The client talks only to the IV proxy (/api/vportal/*); fetch is replaced by
// fixed answers, like in vportalStore.test.js. The flows against the fake
// VPortal server stay in the E2E suite (test_vportal_integration.py).

function jsonResponse(body, status = 200) {
    return {
        ok: status >= 200 && status < 300,
        status,
        json: async () => body,
        text: async () => JSON.stringify(body),
    };
}

function textResponse(text, status) {
    return { ok: false, status, json: async () => { throw new Error('not json'); }, text: async () => text };
}

const LOGIN_ANSWER = { access_token: 'jwt-test', exp: 9999999999, fetch_interval_ms: 3000 };

beforeEach(() => {
    localStorage.clear();
});

afterEach(() => {
    vi.unstubAllGlobals();
});

describe('vportalClient', () => {
    it('exposes login, isConnected and logout', () => {
        expect(typeof vportalClient.login).toBe('function');
        expect(typeof vportalClient.isConnected).toBe('function');
        expect(typeof vportalClient.logout).toBe('function');
    });

    it('login stores token, host and polling interval for the session', async () => {
        const fetchFn = vi.fn(async (url) =>
            url === '/api/vportal/login' ? jsonResponse(LOGIN_ANSWER) : jsonResponse({}, 404));
        vi.stubGlobal('fetch', fetchFn);

        await vportalClient.login('SESSION1', 'bvdk.vportal-online.de', 'u', 'p');

        const stored = JSON.parse(localStorage.getItem('vportal:SESSION1'));
        expect(stored.token).toBe('jwt-test');
        expect(stored.host).toBe('bvdk.vportal-online.de');
        expect(stored.fetch_interval_ms).toBe(3000);
    });

    it('fetchActiveAttempt returns the first attempt of the active group in normalized shape', async () => {
        const answers = {
            COMP_ID: { data: { profile: { competition: { id: 'C-1' } } } },
            GROUP: { data: { competitionGroupList: { competitionGroups: [{ id: 'G-1' }] } } },
            ATHLETES: { data: { competitionAthleteAttemptList: { competitionAthleteAttempts: [{
                id: 'A-1', attempt: 2, discipline: 'SQUAT', weight: 215, status: null,
                competitionAthlete: {
                    firstName: 'Maria', lastName: 'Schneider',
                    club: { name: 'SV Eisenkraft Berlin' },
                    bodyWeightCategory: { name: '-72 kg' },
                    ageCategory: { name: 'Open' },
                },
            }] } } },
        };
        vi.stubGlobal('fetch', vi.fn(async (url, opts) => {
            if (url === '/api/vportal/login') return jsonResponse(LOGIN_ANSWER);
            const { query } = JSON.parse(opts.body);
            if (query.includes('profile')) return jsonResponse(answers.COMP_ID);
            if (query.includes('competitionGroupList')) return jsonResponse(answers.GROUP);
            return jsonResponse(answers.ATHLETES);
        }));

        await vportalClient.login('S1', 'bvdk.vportal-online.de', 'u', 'p');
        vportalClient.setStage('S1', 'STAGE-1', 'Platform 1');
        const attempt = await vportalClient.fetchActiveAttempt('S1');

        expect(attempt).toEqual({
            firstName: 'Maria',
            lastName: 'Schneider',
            club: 'SV Eisenkraft Berlin',
            bodyWeightCategory: '-72 kg',
            ageCategory: 'Open',
            discipline: 'SQUAT',
            attempt: 2,
            weight: 215,
        });
    });

    it('pollActiveAttempt reports token-expired when the proxy answers 401', async () => {
        vi.stubGlobal('fetch', vi.fn(async (url) => {
            if (url === '/api/vportal/login') return jsonResponse({ ...LOGIN_ANSWER, fetch_interval_ms: 100 });
            if (url === '/api/vportal/graphql') return textResponse('expired', 401);
            return jsonResponse({}, 404);
        }));

        await vportalClient.login('S1', 'bvdk.vportal-online.de', 'u', 'p');
        vportalClient.setStage('S1', 'STAGE-1', 'P1');
        const onUpdate = vi.fn();
        const kind = await new Promise((resolve) => {
            vportalClient.pollActiveAttempt('S1', 100, onUpdate, resolve);
        });

        expect(kind).toBe('token-expired');
        expect(onUpdate).not.toHaveBeenCalled();
    });
});
