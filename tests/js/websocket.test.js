import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import {
    createWebSocket,
    WATCHDOG_STALE_MS,
    WATCHDOG_CHECK_MS,
    RETRY_DELAYS_MS,
    RETRY_JITTER,
    retryDelay,
} from '../../src/iron_verdict/static/js/websocket.js';

class FakeWebSocket {
    static CONNECTING = 0;
    static OPEN = 1;
    static CLOSING = 2;
    static CLOSED = 3;
    static instances = [];

    constructor(url) {
        this.url = url;
        this.readyState = FakeWebSocket.CONNECTING;
        this.sent = [];
        this.closeCalls = 0;
        FakeWebSocket.instances.push(this);
    }
    send(data) { this.sent.push(data); }
    close() { this.closeCalls += 1; this.readyState = FakeWebSocket.CLOSING; }

    // Test helpers
    open() { this.readyState = FakeWebSocket.OPEN; this.onopen?.(); }
    receive(msg) { this.onmessage?.({ data: JSON.stringify(msg) }); }
    drop() { this.readyState = FakeWebSocket.CLOSED; this.onclose?.({}); }
}

// Wrappers listen on window/document; close them after each test so a
// leftover wrapper cannot react to the next test's events.
let liveWrappers = [];
afterEach(() => {
    liveWrappers.forEach((w) => w.close());
    liveWrappers = [];
});

function setup() {
    const cb = {
        onMessage: vi.fn(),
        onError: vi.fn(),
        onClose: vi.fn(),
        onReopen: vi.fn(),
        onDropped: vi.fn(),
    };
    const wrapper = createWebSocket('ws://test/ws', cb.onMessage, cb.onError, cb.onClose, cb.onReopen, cb.onDropped);
    liveWrappers.push(wrapper);
    return { wrapper, cb, first: FakeWebSocket.instances[0] };
}

describe('heartbeat watchdog', () => {
    beforeEach(() => {
        vi.useFakeTimers();
        FakeWebSocket.instances = [];
        vi.stubGlobal('WebSocket', FakeWebSocket);
    });
    afterEach(() => {
        vi.useRealTimers();
        vi.unstubAllGlobals();
    });

    it('allows three missed 5 s pings before giving up', () => {
        expect(WATCHDOG_STALE_MS).toBe(15000);
        expect(WATCHDOG_CHECK_MS * 2).toBeLessThan(WATCHDOG_STALE_MS);
    });

    it('reconnects immediately when no message arrives within the stale limit', () => {
        const { cb, first } = setup();
        first.open();

        vi.advanceTimersByTime(WATCHDOG_STALE_MS + WATCHDOG_CHECK_MS);

        expect(first.closeCalls).toBe(1);
        expect(cb.onDropped).toHaveBeenCalledTimes(1);
        expect(FakeWebSocket.instances).toHaveLength(2);
    });

    it('keeps a connection open while pings keep arriving', () => {
        const { cb, first } = setup();
        first.open();

        for (let i = 0; i < 12; i++) {
            vi.advanceTimersByTime(5000);
            first.receive({ type: 'ping' });
        }

        expect(first.closeCalls).toBe(0);
        expect(cb.onDropped).not.toHaveBeenCalled();
        expect(FakeWebSocket.instances).toHaveLength(1);
    });

    it('counts any server message as a sign of life', () => {
        const { first } = setup();
        first.open();

        for (let i = 0; i < 6; i++) {
            vi.advanceTimersByTime(10000);
            first.receive({ type: 'judge_status_update' });
        }

        expect(first.closeCalls).toBe(0);
    });

    it('ignores late events from the abandoned socket', () => {
        const { cb, first } = setup();
        first.open();
        vi.advanceTimersByTime(WATCHDOG_STALE_MS + WATCHDOG_CHECK_MS);

        first.receive({ type: 'show_results' });
        first.drop();

        expect(cb.onMessage).not.toHaveBeenCalled();
        expect(cb.onDropped).toHaveBeenCalledTimes(1);
        vi.advanceTimersByTime(20000);
        expect(FakeWebSocket.instances).toHaveLength(2);
    });

    it('watches the new socket after a forced reconnect', () => {
        const { cb, first } = setup();
        first.open();
        vi.advanceTimersByTime(WATCHDOG_STALE_MS + WATCHDOG_CHECK_MS);
        const second = FakeWebSocket.instances[1];
        second.open();

        expect(cb.onReopen).toHaveBeenCalledTimes(2);
        vi.advanceTimersByTime(WATCHDOG_STALE_MS + WATCHDOG_CHECK_MS);
        expect(second.closeCalls).toBe(1);
        expect(FakeWebSocket.instances).toHaveLength(3);
    });

    it('does not reconnect after timers were paused by the browser', () => {
        const { first } = setup();
        first.open();

        // Simulate a frozen / heavily throttled background tab: the clock jumps
        // a minute ahead without any watchdog check running in between.
        vi.setSystemTime(Date.now() + 60000);
        vi.advanceTimersByTime(WATCHDOG_CHECK_MS);

        expect(first.closeCalls).toBe(0);
        expect(FakeWebSocket.instances).toHaveLength(1);
    });

    it('still detects a dead connection once timers run normally again', () => {
        const { cb, first } = setup();
        first.open();
        vi.setSystemTime(Date.now() + 60000);
        vi.advanceTimersByTime(WATCHDOG_CHECK_MS);

        vi.advanceTimersByTime(WATCHDOG_STALE_MS + WATCHDOG_CHECK_MS);

        expect(cb.onDropped).toHaveBeenCalledTimes(1);
        expect(FakeWebSocket.instances).toHaveLength(2);
    });

    it('does not run after the final close()', () => {
        const { wrapper, cb, first } = setup();
        first.open();
        wrapper.close();

        vi.advanceTimersByTime(60000);

        expect(cb.onDropped).not.toHaveBeenCalled();
        expect(FakeWebSocket.instances).toHaveLength(1);
    });

    it('stops checking while the socket is down and waits for the backoff reconnect', () => {
        const { cb, first } = setup();
        first.open();
        first.drop();
        expect(cb.onDropped).toHaveBeenCalledTimes(1);

        vi.advanceTimersByTime(1000);
        const second = FakeWebSocket.instances[1];
        // Second socket never opens: the watchdog must not pile up extra sockets.
        vi.advanceTimersByTime(WATCHDOG_STALE_MS + WATCHDOG_CHECK_MS);
        expect(second.closeCalls).toBe(0);
        expect(FakeWebSocket.instances).toHaveLength(2);
    });
});

describe('retry delays', () => {
    it('uses 0.5, 1, 2 and 3 s as base waits', () => {
        expect(RETRY_DELAYS_MS).toEqual([500, 1000, 2000, 3000]);
    });

    it('adds at most ±20 % jitter', () => {
        expect(RETRY_JITTER).toBe(0.2);
        expect(retryDelay(3, () => 0)).toBe(2400);
        expect(retryDelay(3, () => 0.999999)).toBeLessThanOrEqual(3600);
        expect(retryDelay(3, () => 0.999999)).toBeGreaterThan(3590);
        expect(retryDelay(0, () => 0)).toBe(400);
    });
});

describe('reconnect scheduling', () => {
    beforeEach(() => {
        vi.useFakeTimers();
        FakeWebSocket.instances = [];
        vi.stubGlobal('WebSocket', FakeWebSocket);
        vi.spyOn(Math, 'random').mockReturnValue(0.5);
        Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true });
    });
    afterEach(() => {
        vi.useRealTimers();
        vi.unstubAllGlobals();
        vi.restoreAllMocks();
    });

    // Drops the newest socket and returns how long the wrapper waited
    // before it created the next one.
    function dropAndMeasure() {
        const count = FakeWebSocket.instances.length;
        FakeWebSocket.instances[count - 1].drop();
        let waited = 0;
        while (FakeWebSocket.instances.length === count) {
            vi.advanceTimersByTime(100);
            waited += 100;
            if (waited > 60000) throw new Error('no reconnect');
        }
        return waited;
    }

    it('waits 0.5, 1, 2, then at most 3 s between failed attempts', () => {
        const { first } = setup();
        first.open();

        const waits = [];
        for (let i = 0; i < 6; i++) waits.push(dropAndMeasure());

        expect(waits).toEqual([500, 1000, 2000, 3000, 3000, 3000]);
    });

    it('starts again at 0.5 s after a successful connection', () => {
        const { first } = setup();
        first.open();
        dropAndMeasure();
        dropAndMeasure();
        dropAndMeasure();

        FakeWebSocket.instances.at(-1).open();

        expect(dropAndMeasure()).toBe(500);
    });

    it.each([
        ['online', () => window.dispatchEvent(new Event('online'))],
        ['visibilitychange', () => document.dispatchEvent(new Event('visibilitychange'))],
        ['pageshow from bfcache', () => {
            const event = new Event('pageshow');
            event.persisted = true;
            window.dispatchEvent(event);
        }],
    ])('%s connects at once while waiting for a retry', (_name, fire) => {
        const { first } = setup();
        first.open();
        dropAndMeasure();
        dropAndMeasure();
        FakeWebSocket.instances.at(-1).drop();
        expect(FakeWebSocket.instances).toHaveLength(3);

        fire();

        expect(FakeWebSocket.instances).toHaveLength(4);
        // The pending retry was cancelled: no second socket follows.
        vi.advanceTimersByTime(10000);
        expect(FakeWebSocket.instances).toHaveLength(4);
    });

    it('ignores a hidden tab becoming hidden', () => {
        const { first } = setup();
        first.open();
        first.drop();
        Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true });

        document.dispatchEvent(new Event('visibilitychange'));

        expect(FakeWebSocket.instances).toHaveLength(1);
    });

    it('ignores a normal pageshow (not from bfcache)', () => {
        const { first } = setup();
        first.open();
        first.drop();

        window.dispatchEvent(new Event('pageshow'));

        expect(FakeWebSocket.instances).toHaveLength(1);
    });

    it('leaves an open socket alone', () => {
        const { first } = setup();
        first.open();

        window.dispatchEvent(new Event('online'));
        document.dispatchEvent(new Event('visibilitychange'));

        expect(first.closeCalls).toBe(0);
        expect(FakeWebSocket.instances).toHaveLength(1);
    });

    it('leaves a connection attempt in progress alone', () => {
        const { first } = setup();
        first.open();
        dropAndMeasure();

        window.dispatchEvent(new Event('online'));

        expect(FakeWebSocket.instances[1].closeCalls).toBe(0);
        expect(FakeWebSocket.instances).toHaveLength(2);
    });

    it('replaces a socket that closed without a close event (page frozen in bfcache)', () => {
        const { cb, first } = setup();
        first.open();
        // Closed while frozen; the close event never reached the wrapper.
        first.readyState = FakeWebSocket.CLOSED;

        const event = new Event('pageshow');
        event.persisted = true;
        window.dispatchEvent(event);

        expect(cb.onDropped).toHaveBeenCalledTimes(1);
        expect(FakeWebSocket.instances).toHaveLength(2);
        // A late close event from the old socket must not add another one.
        first.onclose?.({});
        vi.advanceTimersByTime(10000);
        expect(FakeWebSocket.instances).toHaveLength(2);
    });

    it('does nothing after the final close()', () => {
        const { wrapper, first } = setup();
        first.open();
        wrapper.close();
        first.drop();

        window.dispatchEvent(new Event('online'));
        document.dispatchEvent(new Event('visibilitychange'));
        vi.advanceTimersByTime(10000);

        expect(FakeWebSocket.instances).toHaveLength(1);
    });

    it('removes its window and document listeners on close()', () => {
        const winRemove = vi.spyOn(window, 'removeEventListener');
        const docRemove = vi.spyOn(document, 'removeEventListener');
        const { wrapper } = setup();

        wrapper.close();

        const removed = [...winRemove.mock.calls, ...docRemove.mock.calls].map((c) => c[0]);
        expect(removed).toEqual(expect.arrayContaining(['online', 'pageshow', 'visibilitychange']));
    });
});
