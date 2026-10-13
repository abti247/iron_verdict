import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { createConnection } from '../../src/iron_verdict/static/js/connection.js';
import { createSessionStore } from '../../src/iron_verdict/static/js/sessionStore.js';
import { createNavStore } from '../../src/iron_verdict/static/js/navigation.js';
import { createJudgeStore } from '../../src/iron_verdict/static/js/judgeStore.js';
import { createDisplayStore } from '../../src/iron_verdict/static/js/displayStore.js';
import { createTimerStore } from '../../src/iron_verdict/static/js/timer.js';
import { createSettingsStore } from '../../src/iron_verdict/static/js/settingsStore.js';

const CODE = 'ABCD1234';

function fakeVportal() {
    return {
        startDisplayOverlay: vi.fn().mockResolvedValue(null),
        stopDisplayOverlay: vi.fn(),
        applySessionInfo: vi.fn(),
    };
}

function setup({ fetchFn = vi.fn() } = {}) {
    const sockets = [];
    const openSocket = vi.fn((url, onMessage, onError, onClose, onReopen, onDropped) => {
        const socket = { url, onMessage, onReopen, onDropped, readyState: WebSocket.OPEN, send: vi.fn(), close: vi.fn() };
        sockets.push(socket);
        return socket;
    });
    const history = { pushState: vi.fn(), replaceState: vi.fn() };
    const session = createSessionStore();
    const settings = createSettingsStore();
    let conn = null;
    const stores = {
        session,
        nav: createNavStore(history),
        settings,
        judge: createJudgeStore({ session, settings, send: (data) => conn.send(data), storage: sessionStorage }),
        display: createDisplayStore(),
        timer: createTimerStore(),
        vportal: fakeVportal(),
    };
    const alert = vi.fn();
    conn = createConnection({
        stores,
        storage: sessionStorage,
        location: { protocol: 'http:', host: 'example.test' },
        openSocket,
        fetchFn,
        t: (key) => key,
        alert,
    });
    return { conn, stores, sockets, openSocket, history, alert };
}

// Join `role` and answer with join_success, as the server does.
function joined(env, role, sessionState = {}) {
    env.stores.session.code = CODE;
    env.conn.joinSession(role);
    const socket = env.sockets.at(-1);
    socket.onReopen();
    socket.onMessage({ type: 'join_success', is_head: false, session_state: sessionState });
    return socket;
}

beforeEach(() => {
    sessionStorage.clear();
    vi.useFakeTimers();
});

afterEach(() => {
    vi.useRealTimers();
});

describe('joining a role', () => {
    it('opens one socket and sends join with the stored reconnect token on open', () => {
        const env = setup();
        sessionStorage.setItem('iv_session', JSON.stringify({ code: CODE, role: 'left_judge', reconnect_token: 'tok' }));
        env.stores.session.code = CODE;

        env.conn.joinSession('left_judge');
        expect(env.openSocket).toHaveBeenCalledTimes(1);
        expect(env.sockets[0].url).toBe('ws://example.test/ws');
        expect(env.stores.session.connectionStatus).toBe('reconnecting');

        env.sockets[0].onReopen();
        expect(env.stores.session.connectionStatus).toBe('connected');
        expect(env.sockets[0].send).toHaveBeenCalledWith({
            type: 'join', session_code: CODE, role: 'left_judge', reconnect_token: 'tok',
        });
    });

    it('starts the VPortal display overlay only for the display role', () => {
        const env = setup();
        joined(env, 'left_judge');
        expect(env.stores.vportal.startDisplayOverlay).not.toHaveBeenCalled();

        env.conn.returnToRoleSelection();
        joined(env, 'display');
        expect(env.stores.vportal.startDisplayOverlay).toHaveBeenCalledWith(CODE);
    });

    it('join_success shows the screen of the role and applies the server settings', () => {
        const env = setup();
        joined(env, 'display', { name: 'Meet', settings: { lift_type: 'bench', show_explanations: false, require_reasons: true } });
        expect(env.stores.nav.screen).toBe('display');
        expect(env.stores.session.name).toBe('Meet');
        expect(env.stores.settings).toMatchObject({ liftType: 'bench', showExplanations: false, requireReasons: true });
    });
});

describe('every way out of a session stops the VPortal overlay and closes the socket', () => {
    it('back to role-select', () => {
        const env = setup();
        const socket = joined(env, 'display');
        env.conn.returnToRoleSelection();
        expect(env.stores.vportal.stopDisplayOverlay).toHaveBeenCalled();
        expect(socket.close).toHaveBeenCalled();
        expect(env.stores.nav.screen).toBe('role-select');
        expect(JSON.parse(sessionStorage.getItem('iv_session'))).toEqual({ code: CODE });
    });

    it('back to the landing screen', () => {
        const env = setup();
        const socket = joined(env, 'display');
        env.conn.returnToLanding();
        expect(env.stores.vportal.stopDisplayOverlay).toHaveBeenCalled();
        expect(socket.close).toHaveBeenCalled();
        expect(env.stores.nav.screen).toBe('landing');
        expect(env.stores.session.code).toBe('');
        expect(sessionStorage.getItem('iv_session')).toBeNull();
    });

    it('session ended by the head judge', () => {
        const env = setup();
        env.stores.session.isDemo = true;
        const socket = joined(env, 'display');
        socket.onMessage({ type: 'session_ended' });
        expect(env.stores.vportal.stopDisplayOverlay).toHaveBeenCalled();
        expect(socket.close).toHaveBeenCalled();
        expect(env.alert).toHaveBeenCalledWith('alerts.sessionEnded');
        expect(env.stores.nav.screen).toBe('landing');
        expect(env.stores.session.isDemo).toBe(false);
    });

    it('a final join error', () => {
        const env = setup();
        env.stores.session.code = CODE;
        env.conn.joinSession('display');
        const socket = env.sockets[0];
        socket.onMessage({ type: 'join_error', message: 'Session not found' });
        expect(env.stores.vportal.stopDisplayOverlay).toHaveBeenCalled();
        expect(socket.close).toHaveBeenCalled();
        expect(sessionStorage.getItem('iv_session')).toBeNull();
    });

    it('the browser back button to role-select, without pushing a history entry', () => {
        const env = setup();
        const socket = joined(env, 'display');
        env.history.pushState.mockClear();
        env.conn.followHistory('role-select');
        expect(env.stores.vportal.stopDisplayOverlay).toHaveBeenCalled();
        expect(socket.close).toHaveBeenCalled();
        expect(env.stores.nav.screen).toBe('role-select');
        expect(env.history.pushState).not.toHaveBeenCalled();
        expect(env.stores.nav.handlingPopstate).toBe(false);
    });
});

describe('incoming messages reach the stores', () => {
    it('show_results fills the judge result and, on the display, the display lights', () => {
        const env = setup();
        const socket = joined(env, 'display');
        socket.onMessage({
            type: 'show_results',
            votes: { left: 'white', center: 'red', right: 'white' },
            reasons: { left: null, center: 'reasons.squat.red.depth', right: null },
            showExplanations: true,
            liftType: 'squat',
            timer_frozen_ms: 41200,
        });
        expect(env.stores.judge.resultsShown).toBe(true);
        expect(env.stores.display.phase).toBe('votes');
        expect(env.stores.display.reasons.center).toBe('reasons.squat.red.depth');
        expect(env.stores.display.isValidLift()).toBe(true);
        expect(env.stores.timer.display).toBe('42');
    });

    it('reset_for_next_lift clears the display and the timer', () => {
        const env = setup();
        const socket = joined(env, 'display');
        socket.onMessage({ type: 'show_results', votes: { left: 'red', center: 'red', right: 'red' }, reasons: null });
        socket.onMessage({ type: 'timer_start', time_remaining_ms: 30000 });
        socket.onMessage({ type: 'reset_for_next_lift', lift_id: 2 });
        expect(env.stores.display.phase).toBe('idle');
        expect(env.stores.display.votes).toEqual({ left: null, center: null, right: null });
        expect(env.stores.judge.liftId).toBe(2);
        expect(env.stores.timer.display).toBe('60');
    });

    it('settings_update changes the settings', () => {
        const env = setup();
        const socket = joined(env, 'left_judge');
        socket.onMessage({ type: 'settings_update', liftType: 'deadlift', requireReasons: true });
        expect(env.stores.settings.liftType).toBe('deadlift');
        expect(env.stores.settings.requireReasons).toBe(true);
    });

    it('answers ping with pong', () => {
        const env = setup();
        const socket = joined(env, 'left_judge');
        socket.onMessage({ type: 'ping' });
        expect(socket.send).toHaveBeenCalledWith({ type: 'pong' });
    });

    it('logs an unknown message type instead of dropping it silently', () => {
        const env = setup();
        const socket = joined(env, 'left_judge');
        const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
        try {
            socket.onMessage({ type: 'something_new' });
            expect(warn).toHaveBeenCalledWith(expect.any(String), 'something_new');
        } finally {
            warn.mockRestore();
        }
    });
});

describe('session lookup and reload recovery', () => {
    it('a found session leads to role-select', async () => {
        const fetchFn = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ kind: 'vportal' }) });
        const env = setup({ fetchFn });
        env.stores.session.joinCode = 'abcd1234';
        await env.conn.lookupSession();
        expect(fetchFn).toHaveBeenCalledWith('/api/sessions/' + CODE);
        expect(env.stores.session.code).toBe(CODE);
        expect(env.stores.session.kind).toBe('vportal');
        expect(env.stores.nav.screen).toBe('role-select');
    });

    it('an unknown code shows an inline error on the landing screen', async () => {
        const fetchFn = vi.fn().mockResolvedValue({ ok: false, status: 404 });
        const env = setup({ fetchFn });
        env.stores.session.joinCode = CODE;
        await env.conn.lookupSession();
        expect(env.stores.nav.screen).toBe('landing');
        expect(env.stores.session.joinError).toBe('landing.sessionNotFound');
    });

    it('a stored judge session is rejoined behind the reconnecting screen', () => {
        const env = setup();
        sessionStorage.setItem('iv_session', JSON.stringify({ code: CODE, role: 'left_judge' }));
        env.conn.start();
        expect(env.stores.nav.screen).toBe('reconnecting');
        expect(env.openSocket).toHaveBeenCalledTimes(1);
        env.sockets[0].onReopen();
        env.sockets[0].onMessage({ type: 'join_success', is_head: false, session_state: {} });
        expect(env.stores.nav.screen).toBe('judge');
        // The reload keeps the back-stack depth: the screen change replaces the entry.
        expect(env.history.replaceState).toHaveBeenCalledWith({ screen: 'judge' }, '', '/');
    });
});
