import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { createPauseStore, formatPauseRemaining, PAUSE_TICK_MS } from '../../src/iron_verdict/static/js/pauseStore.js';
import { handlePauseUpdate, handlePauseRejected, handleJoinSuccess } from '../../src/iron_verdict/static/js/handlers.js';

const MIN = 60_000;

describe('formatPauseRemaining', () => {
    it.each([
        [0, '0:00'],
        [1, '0:01'],
        [999, '0:01'],
        [1000, '0:01'],
        [9 * MIN + 41_000, '9:41'],
        [10 * MIN, '10:00'],
        [60 * MIN, '1:00:00'],
        [65 * MIN + 5000, '1:05:05'],
        [-5000, '0:00'],
    ])('formats %p ms as %p', (ms, text) => {
        expect(formatPauseRemaining(ms)).toBe(text);
    });
});

describe('pause store', () => {
    let clock;
    let store;

    beforeEach(() => {
        vi.useFakeTimers();
        clock = 1_000_000;
        store = createPauseStore({ now: () => clock });
    });

    afterEach(() => {
        store.apply(null);
        vi.useRealTimers();
    });

    const pause = (overrides = {}) => ({ end_at_ms: 2_000_000 + 10 * MIN, mode: 'minutes', until: null, next_lift: 'bench', ...overrides });

    it('starts without a pause', () => {
        expect(store.active).toBe(false);
        expect(store.pause).toBe(null);
    });

    it('counts down against the server clock, not the device clock', () => {
        // The device clock is 1 000 000 ms behind the server.
        store.apply(pause(), 2_000_000);
        expect(store.active).toBe(true);
        expect(store.pause).toEqual({ endAtMs: 2_000_000 + 10 * MIN, mode: 'minutes', until: null, nextLift: 'bench' });
        expect(store.remainingText()).toBe('10:00');
        clock += 19_000;
        vi.advanceTimersByTime(PAUSE_TICK_MS);
        expect(store.remainingText()).toBe('9:41');
    });

    it('stops at 0:00 and waits for the server to end the pause', () => {
        store.apply(pause(), 2_000_000);
        clock += 11 * MIN;
        vi.advanceTimersByTime(PAUSE_TICK_MS);
        expect(store.remainingText()).toBe('0:00');
        expect(store.active).toBe(true);
    });

    it('stops ticking when the pause ends', () => {
        store.apply(pause(), 2_000_000);
        store.apply(null, 2_000_000);
        expect(store.active).toBe(false);
        expect(vi.getTimerCount()).toBe(0);
    });

    it('keeps the last clock offset when an update carries no server time', () => {
        store.apply(pause(), 2_000_000);
        store.apply(pause({ end_at_ms: 2_000_000 + 5 * MIN }));
        expect(store.remainingText()).toBe('5:00');
    });

    it('confirms a request when the server answers with an update', () => {
        store.requestSent();
        expect(store.pending).toBe(true);
        store.apply(pause(), 2_000_000);
        expect(store.pending).toBe(false);
        expect(store.confirmedChanges).toBe(1);
        // An update this display did not ask for confirms nothing.
        store.apply(null, 2_000_000);
        expect(store.confirmedChanges).toBe(1);
    });

    it('shows a rejection and clears it with the next request', () => {
        store.requestSent();
        store.rejected('past');
        expect(store.pending).toBe(false);
        expect(store.error).toBe('past');
        store.requestSent();
        expect(store.error).toBe('');
    });

    it('takes the state of a (re)join as the truth and drops a pending request', () => {
        store.requestSent();
        store.joined(pause(), 2_000_000);
        expect(store.pending).toBe(false);
        expect(store.confirmedChanges).toBe(0);
        expect(store.active).toBe(true);
        store.joined(null, 2_000_000);
        expect(store.active).toBe(false);
    });
});

describe('pause handlers', () => {
    let store;

    beforeEach(() => {
        vi.useFakeTimers();
        store = createPauseStore({ now: () => 0 });
    });

    afterEach(() => {
        store.apply(null);
        vi.useRealTimers();
    });

    const conn = (role) => ({ session: { role }, pause: store });

    it('applies pause_update on a display', () => {
        handlePauseUpdate(conn('display'), { type: 'pause_update', pause: { end_at_ms: MIN, mode: 'until', until: '13:15', next_lift: null }, server_now_ms: 0 });
        expect(store.pause).toEqual({ endAtMs: MIN, mode: 'until', until: '13:15', nextLift: null });
    });

    it('ignores pause_update on a judge device', () => {
        handlePauseUpdate(conn('left_judge'), { type: 'pause_update', pause: { end_at_ms: MIN, mode: 'minutes', until: null, next_lift: null }, server_now_ms: 0 });
        expect(store.active).toBe(false);
    });

    it('shows pause_rejected', () => {
        store.requestSent();
        handlePauseRejected(conn('display'), { type: 'pause_rejected', code: 'too_long' });
        expect(store.error).toBe('too_long');
    });

    it('takes the pause from join_success on a display', () => {
        store.requestSent();
        const c = {
            ...conn('display'),
            session: { role: 'display', judgeConnected: {} },
            roleTaken: { reset: () => {} },
            nav: { navigateTo: () => {} },
            judge: {},
            settings: {},
            storage: { getItem: () => null },
            timer: { start: () => {} },
        };
        handleJoinSuccess(c, {
            is_head: false,
            session_state: { pause: { end_at_ms: MIN, mode: 'minutes', until: null, next_lift: null }, server_now_ms: 0 },
        });
        expect(store.active).toBe(true);
        expect(store.pending).toBe(false);
    });
});
