import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { createVportalStore } from '../../src/iron_verdict/static/js/vportalStore.js';

const t = (key) => `t:${key}`;

function fakeClient(overrides = {}) {
    return {
        login: vi.fn().mockResolvedValue(undefined),
        fetchStages: vi.fn().mockResolvedValue([{ id: 'S1', name: 'Platform A' }, { id: 'S2', name: 'Platform B' }]),
        setStage: vi.fn(),
        logout: vi.fn(),
        isConnected: vi.fn().mockReturnValue(true),
        getStored: vi.fn().mockReturnValue({ stage_id: 'S1', fetch_interval_ms: 2500 }),
        pollActiveAttempt: vi.fn().mockReturnValue(() => {}),
        ...overrides,
    };
}

function jsonResponse(body, ok = true) {
    return { ok, json: async () => body };
}

function makeStore({ client = fakeClient(), fetchFn = vi.fn() } = {}) {
    return { store: createVportalStore({ client, t, fetchFn }), client, fetchFn };
}

describe('connect dialog', () => {
    beforeEach(() => { delete window._testVportalHost; });

    it('opens on the federation step when not connected', () => {
        const { store } = makeStore();
        store.openModal();
        expect(store.modalOpen).toBe(true);
        expect(store.modalStep).toBe('federation');
    });

    it('opens on the connected step when already connected', () => {
        const { store } = makeStore();
        store.connected = true;
        store.openModal();
        expect(store.modalStep).toBe('connected');
    });

    it('logs in with the host of the chosen federation, then lists stages and preselects the first', async () => {
        const { store, client } = makeStore();
        store.federation = 'OEVK';
        store.identity = 'u';
        store.credential = 'p';
        await store.doLogin('ABCD1234');
        expect(client.login).toHaveBeenCalledWith('ABCD1234', 'oevk.vportal-online.de', 'u', 'p');
        expect(client.fetchStages).toHaveBeenCalledWith('ABCD1234');
        expect(store.modalStep).toBe('stage');
        expect(store.federationLabel).toBe('OEVK');
        expect(store.stages.map(s => s.id)).toEqual(['S1', 'S2']);
        expect(store.selectedStage).toBe('S1');
    });

    it('maps each federation to its VPortal host', () => {
        const { store } = makeStore();
        expect(store._hostForFederation('BVDK')).toBe('bvdk.vportal-online.de');
        expect(store._hostForFederation('OEVK')).toBe('oevk.vportal-online.de');
        expect(store._hostForFederation('BVDK_STAGING')).toBe('staging-bvdk.vportal-online.de');
        expect(store._hostForFederation('???')).toBe('bvdk.vportal-online.de');
    });

    it('routes to the test host when window._testVportalHost is set', () => {
        const { store } = makeStore();
        window._testVportalHost = 'localhost:9999';
        expect(store._hostForFederation('OEVK')).toBe('localhost:9999');
    });

    it('shows the login error and stays on the credentials step when login fails', async () => {
        const err = new Error('vportal-proxy-error:401');
        err.status = 401;
        const { store, client } = makeStore({ client: fakeClient({ login: vi.fn().mockRejectedValue(err) }) });
        store.modalStep = 'credentials';
        await store.doLogin('ABCD1234');
        expect(store.loginError).toBe('t:vportal.loginFailed');
        expect(store.modalStep).toBe('credentials');
        expect(client.fetchStages).not.toHaveBeenCalled();
    });

    it('clears a previous stage list before a new login', async () => {
        let resolveLogin;
        const login = vi.fn(() => new Promise((r) => { resolveLogin = r; }));
        const { store } = makeStore({ client: fakeClient({ login }) });
        store.stages = [{ id: 'OLD', name: 'Old' }];
        store.selectedStage = 'OLD';
        const pending = store.doLogin('ABCD1234');
        expect(store.stages).toEqual([]);
        expect(store.selectedStage).toBe('');
        resolveLogin();
        await pending;
    });

    it('confirming a stage stores it, marks connected and closes the dialog', () => {
        const { store, client } = makeStore();
        store.stages = [{ id: 'S1', name: 'Platform A' }, { id: 'S2', name: 'Platform B' }];
        store.selectedStage = 'S2';
        store.modalOpen = true;
        store.confirmStage('ABCD1234');
        expect(client.setStage).toHaveBeenCalledWith('ABCD1234', 'S2', 'Platform B');
        expect(store.stageName).toBe('Platform B');
        expect(store.connected).toBe(true);
        expect(store.modalOpen).toBe(false);
    });

    it('disconnecting logs out and resets the connection', () => {
        const { store, client } = makeStore();
        Object.assign(store, { connected: true, stageName: 'Platform A', modalOpen: true });
        store.disconnect('ABCD1234');
        expect(client.logout).toHaveBeenCalledWith('ABCD1234');
        expect(store.connected).toBe(false);
        expect(store.stageName).toBe('');
        expect(store.modalOpen).toBe(false);
    });
});

describe('session info', () => {
    it('applies the staging flag from a session lookup', () => {
        const { store } = makeStore();
        store.applySessionInfo({ kind: 'vportal', staging_available: true });
        expect(store.stagingAvailable).toBe(true);
        store.applySessionInfo(null);
        expect(store.stagingAvailable).toBe(false);
    });

    it('loads the staging flag for a freshly created session', async () => {
        const fetchFn = vi.fn().mockResolvedValue(jsonResponse({ kind: 'vportal', staging_available: true }));
        const { store } = makeStore({ fetchFn });
        await store.loadStagingFlag('ABCD1234');
        expect(fetchFn).toHaveBeenCalledWith('/api/sessions/ABCD1234');
        expect(store.stagingAvailable).toBe(true);
    });

    it('keeps the staging option hidden when the lookup fails', async () => {
        const { store } = makeStore({ fetchFn: vi.fn().mockRejectedValue(new Error('offline')) });
        await store.loadStagingFlag('ABCD1234');
        expect(store.stagingAvailable).toBe(false);
    });
});

describe('display overlay', () => {
    it('starts polling for a vportal session and returns its kind', async () => {
        const fetchFn = vi.fn().mockResolvedValue(jsonResponse({ kind: 'vportal', staging_available: false }));
        const { store, client } = makeStore({ fetchFn });
        const kind = await store.startDisplayOverlay('ABCD1234');
        expect(kind).toBe('vportal');
        expect(client.pollActiveAttempt).toHaveBeenCalledWith('ABCD1234', 2500, expect.any(Function), expect.any(Function));
    });

    it('does not poll for a generic session', async () => {
        const fetchFn = vi.fn().mockResolvedValue(jsonResponse({ staging_available: false }));
        const { store, client } = makeStore({ fetchFn });
        expect(await store.startDisplayOverlay('ABCD1234')).toBe('generic');
        expect(client.pollActiveAttempt).not.toHaveBeenCalled();
    });

    it('does not poll when this device has no VPortal stage', async () => {
        const fetchFn = vi.fn().mockResolvedValue(jsonResponse({ kind: 'vportal' }));
        const client = fakeClient({ getStored: vi.fn().mockReturnValue({}) });
        const { store } = makeStore({ client, fetchFn });
        await store.startDisplayOverlay('ABCD1234');
        expect(client.pollActiveAttempt).not.toHaveBeenCalled();
    });

    it('shows each attempt, keeps the last one on a stale tick, and shows the banner on errors', async () => {
        const fetchFn = vi.fn().mockResolvedValue(jsonResponse({ kind: 'vportal' }));
        const { store, client } = makeStore({ fetchFn });
        await store.startDisplayOverlay('ABCD1234');
        const [, , onUpdate, onError] = client.pollActiveAttempt.mock.calls[0];

        onUpdate({ firstName: 'Maria' });
        expect(store.displayAttempt).toEqual({ firstName: 'Maria' });
        onUpdate({ __stale: true });
        expect(store.displayAttempt).toEqual({ firstName: 'Maria' });

        onError('upstream-unreachable');
        expect(store.displayAttempt).toBeNull();
        expect(store.disconnectedReason).toBe('upstream-unreachable');

        onUpdate({ firstName: 'Anna' });
        expect(store.displayAttempt).toEqual({ firstName: 'Anna' });
        expect(store.disconnectedReason).toBe('');
    });
});

describe('display overlay start and stop', () => {
    afterEach(() => { vi.useRealTimers(); });

    it('retries a failed session lookup on a VPortal-connected device and shows the banner meanwhile', async () => {
        vi.useFakeTimers();
        const fetchFn = vi.fn()
            .mockRejectedValueOnce(new Error('offline'))
            .mockResolvedValueOnce(jsonResponse({}, false))
            .mockResolvedValue(jsonResponse({ kind: 'vportal' }));
        const { store, client } = makeStore({ fetchFn });
        const started = store.startDisplayOverlay('ABCD1234');

        await vi.advanceTimersByTimeAsync(0);
        expect(store.disconnectedReason).toBe('session-lookup-failed');
        expect(client.pollActiveAttempt).not.toHaveBeenCalled();

        await vi.advanceTimersByTimeAsync(2500);
        expect(fetchFn).toHaveBeenCalledTimes(2);
        expect(client.pollActiveAttempt).not.toHaveBeenCalled();

        await vi.advanceTimersByTimeAsync(2500);
        expect(fetchFn).toHaveBeenCalledTimes(3);
        expect(await started).toBe('vportal');
        expect(client.pollActiveAttempt).toHaveBeenCalledTimes(1);
    });

    it('does not retry the lookup on a device without a VPortal login', async () => {
        vi.useFakeTimers();
        const fetchFn = vi.fn().mockRejectedValue(new Error('offline'));
        const client = fakeClient({ isConnected: vi.fn().mockReturnValue(false) });
        const { store } = makeStore({ client, fetchFn });
        expect(await store.startDisplayOverlay('ABCD1234')).toBeNull();
        await vi.advanceTimersByTimeAsync(10000);
        expect(fetchFn).toHaveBeenCalledTimes(1);
        expect(store.disconnectedReason).toBe('');
    });

    it('stops retrying the lookup once the display is left', async () => {
        vi.useFakeTimers();
        const fetchFn = vi.fn().mockRejectedValue(new Error('offline'));
        const { store, client } = makeStore({ fetchFn });
        store.startDisplayOverlay('ABCD1234');
        await vi.advanceTimersByTimeAsync(0);
        store.stopDisplayOverlay();
        expect(store.disconnectedReason).toBe('');
        fetchFn.mockResolvedValue(jsonResponse({ kind: 'vportal' }));
        await vi.advanceTimersByTimeAsync(10000);
        expect(fetchFn).toHaveBeenCalledTimes(1);
        expect(client.pollActiveAttempt).not.toHaveBeenCalled();
    });

    it('does not start polling when the display is left while the lookup is still running', async () => {
        let resolveLookup;
        const fetchFn = vi.fn().mockReturnValue(new Promise(r => { resolveLookup = r; }));
        const { store, client } = makeStore({ fetchFn });
        const started = store.startDisplayOverlay('ABCD1234');
        store.stopDisplayOverlay();
        resolveLookup(jsonResponse({ kind: 'vportal' }));
        expect(await started).toBeNull();
        expect(client.pollActiveAttempt).not.toHaveBeenCalled();
    });

    it('leaving the display stops the poller and clears the overlay', async () => {
        const stop = vi.fn();
        const fetchFn = vi.fn().mockResolvedValue(jsonResponse({ kind: 'vportal' }));
        const { store, client } = makeStore({ client: fakeClient({ pollActiveAttempt: vi.fn().mockReturnValue(stop) }), fetchFn });
        await store.startDisplayOverlay('ABCD1234');
        const [, , onUpdate] = client.pollActiveAttempt.mock.calls[0];
        onUpdate({ firstName: 'Maria' });
        store.stopDisplayOverlay();
        expect(stop).toHaveBeenCalledTimes(1);
        expect(store.displayAttempt).toBeNull();
    });

    it('starting the display again stops the previous poller, so only one runs', async () => {
        const stops = [vi.fn(), vi.fn()];
        const pollActiveAttempt = vi.fn().mockReturnValueOnce(stops[0]).mockReturnValueOnce(stops[1]);
        const fetchFn = vi.fn().mockResolvedValue(jsonResponse({ kind: 'vportal' }));
        const { store } = makeStore({ client: fakeClient({ pollActiveAttempt }), fetchFn });
        await store.startDisplayOverlay('ABCD1234');
        await store.startDisplayOverlay('ABCD1234');
        expect(pollActiveAttempt).toHaveBeenCalledTimes(2);
        expect(stops[0]).toHaveBeenCalledTimes(1);
        expect(stops[1]).not.toHaveBeenCalled();
    });
});
