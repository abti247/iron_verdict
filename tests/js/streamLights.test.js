import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import {
    LIGHTS_DURATION_STORAGE_KEY, LIGHTS_DURATIONS, loadLightsDuration, saveLightsDuration,
} from '../../src/iron_verdict/static/js/streamLights.js';
import { createDisplayStore } from '../../src/iron_verdict/static/js/displayStore.js';
import { handleJoinSuccess, handleShowResults, handleResetForNextLift } from '../../src/iron_verdict/static/js/handlers.js';
import { displayStreamLights } from '../../src/iron_verdict/static/js/screens/displayStreamLights.js';

// Stream overlay lights only after the decision (#216): the stored duration,
// which results count as live (only those show in the stream), and when the
// overlay hides them again.

const RESULT = {
    votes: { left: 'red', center: 'white', right: 'white' },
    reasons: { left: 'Depth', center: null, right: null },
    showExplanations: true,
    liftType: 'squat',
};

function memoryStorage(initial = {}) {
    const data = { ...initial };
    return {
        getItem: (k) => (k in data ? data[k] : null),
        setItem: (k, v) => { data[k] = String(v); },
        data,
    };
}

describe('lights duration of the stream overlay (per device)', () => {
    it('offers "always" and 3 to 15 seconds', () => {
        expect(LIGHTS_DURATIONS).toEqual(['always', 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]);
    });

    it('is 5 seconds without a stored choice, for an unknown value and with blocked storage', () => {
        expect(loadLightsDuration(memoryStorage())).toBe(5);
        expect(loadLightsDuration(memoryStorage({ [LIGHTS_DURATION_STORAGE_KEY]: '2' }))).toBe(5);
        expect(loadLightsDuration(memoryStorage({ [LIGHTS_DURATION_STORAGE_KEY]: 'x' }))).toBe(5);
        expect(loadLightsDuration(null)).toBe(5);
    });

    it('stores a number of seconds and "always"', () => {
        const s = memoryStorage();
        expect(saveLightsDuration(s, 12)).toBe(true);
        expect(loadLightsDuration(s)).toBe(12);
        expect(saveLightsDuration(s, 'always')).toBe(true);
        expect(loadLightsDuration(s)).toBe('always');
    });

    it('reports a failed save', () => {
        expect(saveLightsDuration(null, 5)).toBe(false);
        expect(saveLightsDuration({ setItem: () => { throw new Error('quota'); } }, 5)).toBe(false);
    });
});

function conn(display) {
    return {
        session: { role: 'display', judgeConnected: {} },
        roleTaken: { reset() {} },
        nav: { navigateTo() {} },
        judge: { showResults() {}, resetVoting() {}, reconcileVoteAfterJoin() {}, voteState: 'idle' },
        timer: { freeze() {}, reset() {}, start() {} },
        settings: {},
        pause: { joined() {} },
        storage: memoryStorage(),
        sendSettings() {},
        t: (k) => k,
        display,
    };
}

function showResults(c) {
    handleShowResults(c, { type: 'show_results', ...RESULT, reasons: { left: 'Depth', center: null, right: null } });
}

describe('live and restored results in the display store', () => {
    let display;
    let c;
    beforeEach(() => {
        display = createDisplayStore();
        c = conn(display);
    });

    it('a result that arrives live is shown in the stream and counted', () => {
        handleJoinSuccess(c, { session_state: { phase: 'voting' } });
        showResults(c);
        expect(display.phase).toBe('votes');
        expect(display.streamShown).toBe(true);
        expect(display.liveResults).toBe(1);
    });

    it('the result replayed after a join in the results phase is not shown again', () => {
        handleJoinSuccess(c, { session_state: { phase: 'results' } });
        showResults(c);
        expect(display.phase).toBe('votes');
        expect(display.streamShown).toBe(false);
        expect(display.liveResults).toBe(0);
        // The next live result shows again.
        handleResetForNextLift(c, { lift_id: 2 });
        showResults(c);
        expect(display.streamShown).toBe(true);
    });

    it('a reconnect while the result still shows neither hides nor restarts it', () => {
        showResults(c);
        handleJoinSuccess(c, { session_state: { phase: 'results' } });
        showResults(c);
        expect(display.streamShown).toBe(true);
        expect(display.liveResults).toBe(1);
    });

    it('the next lift clears it, also an expected replay that never came', () => {
        handleJoinSuccess(c, { session_state: { phase: 'results' } });
        handleResetForNextLift(c, { lift_id: 2 });
        showResults(c);
        expect(display.streamShown).toBe(true);
        handleResetForNextLift(c, { lift_id: 3 });
        expect(display.streamShown).toBe(false);
    });

    it('hideFromStream hides the shown result', () => {
        showResults(c);
        display.hideFromStream();
        expect(display.streamShown).toBe(false);
        expect(display.phase).toBe('votes');
    });
});

function screen({ overlay = true, storage = memoryStorage() } = {}) {
    const display = createDisplayStore();
    const watchers = {};
    const component = {
        ...displayStreamLights(),
        layoutEditing: false,
        $store: { display, session: { overlay }, pause: { active: false } },
        $watch: (expr, fn) => { watchers[expr] = fn; },
    };
    vi.stubGlobal('localStorage', storage);
    component.initDisplayStreamLights();
    // What the store change would trigger through Alpine.
    component.live = () => { display.showResults({ ...RESULT, live: true }); watchers['$store.display.liveResults'](); };
    component.pause = (active) => { component.$store.pause.active = active; watchers['$store.pause.active'](active); };
    return component;
}

describe('stream overlay lights visibility', () => {
    beforeEach(() => { vi.useFakeTimers(); });
    afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

    it('hidden without a result, shown with a live one, hidden after the duration', () => {
        const c = screen();
        expect(c.streamLightsVisible()).toBe(false);
        c.live();
        expect(c.streamLightsVisible()).toBe(true);
        vi.advanceTimersByTime(4999);
        expect(c.streamLightsVisible()).toBe(true);
        vi.advanceTimersByTime(1);
        expect(c.streamLightsVisible()).toBe(false);
    });

    it('uses the stored duration', () => {
        const c = screen({ storage: memoryStorage({ [LIGHTS_DURATION_STORAGE_KEY]: '3' }) });
        expect(c.overlayLightsDuration).toBe(3);
        c.live();
        vi.advanceTimersByTime(3000);
        expect(c.streamLightsVisible()).toBe(false);
    });

    it('a new live result restarts the duration', () => {
        const c = screen();
        c.live();
        vi.advanceTimersByTime(4000);
        c.$store.display.clear();
        c.live();
        vi.advanceTimersByTime(4000);
        expect(c.streamLightsVisible()).toBe(true);
        vi.advanceTimersByTime(1000);
        expect(c.streamLightsVisible()).toBe(false);
    });

    it('the next lift hides at once and the old timer does not hide the next result', () => {
        const c = screen();
        c.live();
        c.$store.display.clear();
        expect(c.streamLightsVisible()).toBe(false);
        vi.advanceTimersByTime(2000);
        c.live();
        vi.advanceTimersByTime(3500);
        expect(c.streamLightsVisible()).toBe(true);
    });

    it('a pause hides the result for good', () => {
        const c = screen();
        c.live();
        c.pause(true);
        c.pause(false);
        expect(c.streamLightsVisible()).toBe(false);
    });

    it('"always" keeps today\'s behaviour: visible with any result, also a restored one', () => {
        const c = screen();
        c.setOverlayLightsDuration('always');
        c.$store.display.showResults({ ...RESULT, live: false });
        expect(c.streamLightsVisible()).toBe(true);
        c.live();
        vi.advanceTimersByTime(60000);
        expect(c.streamLightsVisible()).toBe(true);
        c.$store.display.clear();
        expect(c.streamLightsVisible()).toBe(true);
    });

    it('stores the chosen duration and reports a failed save', () => {
        const storage = memoryStorage();
        const c = screen({ storage });
        c.setOverlayLightsDuration(9);
        expect(storage.data[LIGHTS_DURATION_STORAGE_KEY]).toBe('9');
        expect(c.overlayLightsDurationSaveError).toBe(false);
        vi.stubGlobal('localStorage', { getItem: () => null, setItem: () => { throw new Error('quota'); } });
        c.setOverlayLightsDuration(10);
        expect(c.overlayLightsDuration).toBe(10);
        expect(c.overlayLightsDurationSaveError).toBe(true);
    });

    it('always visible in the layout editor and on the hall display', () => {
        const c = screen();
        c.layoutEditing = true;
        expect(c.streamLightsVisible()).toBe(true);
        expect(screen({ overlay: false }).streamLightsVisible()).toBe(true);
    });

    it('classes: none on the hall display, fade only while a result goes', () => {
        expect(screen({ overlay: false }).streamLightsClass()).toBe('');
        const c = screen();
        expect(c.streamLightsClass()).toBe('stream-lights-hide');
        c.live();
        expect(c.streamLightsClass()).toBe('stream-lights-on');
        vi.advanceTimersByTime(5000);
        expect(c.streamLightsClass()).toBe('stream-lights-hide stream-lights-fade');
        c.$store.display.clear();
        expect(c.streamLightsClass()).toBe('stream-lights-hide');
    });
});
