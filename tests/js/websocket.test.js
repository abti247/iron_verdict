import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import {
    createWebSocket,
    WATCHDOG_STALE_MS,
    WATCHDOG_CHECK_MS,
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

function setup() {
    const cb = {
        onMessage: vi.fn(),
        onError: vi.fn(),
        onClose: vi.fn(),
        onReopen: vi.fn(),
        onDropped: vi.fn(),
    };
    const wrapper = createWebSocket('ws://test/ws', cb.onMessage, cb.onError, cb.onClose, cb.onReopen, cb.onDropped);
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
