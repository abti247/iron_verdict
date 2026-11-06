import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { createDisplayStore } from '../../src/iron_verdict/static/js/displayStore.js';
import { createTimerStore } from '../../src/iron_verdict/static/js/timer.js';
import { handleJoinSuccess, handleShowResults } from '../../src/iron_verdict/static/js/handlers.js';

// A (re)join takes lights and timer from the server's session state (#232):
// a device that missed "Next Lift" or a timer reset while offline must not keep
// showing the old state, and an expired timer shows as expired after a reload.

const RESULT = {
    votes: { left: 'red', center: 'white', right: 'white' },
    reasons: { left: null, center: null, right: null },
    showExplanations: false,
    liftType: 'squat',
};

function conn(role, display, timer) {
    return {
        session: { role, judgeConnected: {} },
        roleTaken: { reset() {} },
        nav: { navigateTo() {} },
        judge: { showResults() {}, reconcileVoteAfterJoin() {}, liftId: null },
        timer,
        settings: {},
        pause: { joined() {} },
        storage: { getItem: () => null, setItem() {} },
        sendSettings() {},
        t: (k) => k,
        display,
    };
}

describe('handleJoinSuccess restores lights and timer from the server', () => {
    let display;
    let timer;
    beforeEach(() => {
        vi.useFakeTimers();
        display = createDisplayStore();
        timer = createTimerStore();
    });
    afterEach(() => {
        timer.reset();
        vi.useRealTimers();
    });

    it('clears the previous lifter\'s lights on a display that missed Next Lift', () => {
        const c = conn('display', display, timer);
        handleShowResults(c, { type: 'show_results', ...RESULT, timer_frozen_ms: 42000 });
        expect(display.phase).toBe('votes');

        handleJoinSuccess(c, { session_state: { phase: 'voting', time_remaining_ms: null } });

        expect(display.phase).toBe('idle');
        expect(display.votes).toEqual({ left: null, center: null, right: null });
        expect(timer.display).toBe('60');
        expect(timer.expired).toBe(false);
    });

    it('keeps the lights and the frozen timer in the results phase (the replayed result fills them)', () => {
        const c = conn('display', display, timer);
        handleShowResults(c, { type: 'show_results', ...RESULT, timer_frozen_ms: 42000 });

        handleJoinSuccess(c, { session_state: { phase: 'results', time_remaining_ms: null } });

        expect(display.phase).toBe('votes');
        expect(timer.display).toBe('42');
        // The replay that follows is restored, not live (#216).
        expect(display.restoredResultExpected).toBe(true);
    });

    it('resets a countdown the server no longer runs', () => {
        const c = conn('display', display, timer);
        timer.start(30000);
        vi.advanceTimersByTime(5000);
        expect(timer.display).toBe(25);

        handleJoinSuccess(c, { session_state: { phase: 'voting', time_remaining_ms: null } });
        vi.advanceTimersByTime(5000);

        expect(timer.display).toBe('60');
        expect(timer.expired).toBe(false);
    });

    it('starts the countdown with the remaining time', () => {
        const c = conn('display', display, timer);
        handleJoinSuccess(c, { session_state: { phase: 'voting', time_remaining_ms: 30000 } });
        vi.advanceTimersByTime(200);
        expect(timer.display).toBe(30);
        expect(timer.expired).toBe(false);
    });

    it.each(['display', 'left_judge'])('shows an expired timer as expired right away (%s)', (role) => {
        const c = conn(role, display, timer);
        handleJoinSuccess(c, { session_state: { phase: 'voting', time_remaining_ms: 0 } });
        expect(timer.display).toBe('0');
        expect(timer.expired).toBe(true);
    });

    it('resets a judge\'s stale countdown too', () => {
        const c = conn('left_judge', display, timer);
        timer.start(30000);
        vi.advanceTimersByTime(1000);

        handleJoinSuccess(c, { session_state: { phase: 'voting', time_remaining_ms: null } });

        expect(timer.display).toBe('60');
    });
});
