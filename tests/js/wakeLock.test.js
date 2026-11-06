import { describe, it, expect, vi } from 'vitest';
import {
    createScreenWakeLock,
    keepsScreenAwake,
} from '../../src/iron_verdict/static/js/wakeLock.js';

// Minimal stand-ins for navigator.wakeLock and its WakeLockSentinel.
class FakeSentinel extends EventTarget {
    constructor() {
        super();
        this.type = 'screen';
        this.released = false;
    }

    async release() {
        if (this.released) return;
        this.released = true;
        this.dispatchEvent(new Event('release'));
    }
}

function fakeWakeLock() {
    const api = {
        sentinels: [],
        rejectNext: null,
        deferNext: false,
        deferred: [],
        request: vi.fn((type) => {
            if (api.rejectNext) {
                const err = api.rejectNext;
                api.rejectNext = null;
                return Promise.reject(err);
            }
            const sentinel = new FakeSentinel();
            sentinel.requestedType = type;
            api.sentinels.push(sentinel);
            if (api.deferNext) {
                api.deferNext = false;
                return new Promise((resolve) => api.deferred.push(() => resolve(sentinel)));
            }
            return Promise.resolve(sentinel);
        }),
        held() {
            return api.sentinels.filter((s) => !s.released);
        },
    };
    return api;
}

function fakeDocument(visibilityState = 'visible') {
    const doc = new EventTarget();
    doc.visibilityState = visibilityState;
    doc.setVisibility = (state) => {
        doc.visibilityState = state;
        doc.dispatchEvent(new Event('visibilitychange'));
    };
    return doc;
}

const flush = () => new Promise((resolve) => setTimeout(resolve, 0));

describe('keepsScreenAwake', () => {
    it('is true for the judge and display screens only', () => {
        expect(keepsScreenAwake('judge')).toBe(true);
        expect(keepsScreenAwake('display')).toBe(true);
        for (const screen of ['landing', 'contact', 'demoIntro', 'reconnecting', 'roleSelect']) {
            expect(keepsScreenAwake(screen)).toBe(false);
        }
    });
});

describe('screen wake lock', () => {
    it('requests a screen wake lock when wanted', async () => {
        const wakeLock = fakeWakeLock();
        const lock = createScreenWakeLock({ wakeLock, doc: fakeDocument() });

        lock.setWanted(true);
        await flush();

        expect(wakeLock.request).toHaveBeenCalledTimes(1);
        expect(wakeLock.request).toHaveBeenCalledWith('screen');
        expect(wakeLock.held()).toHaveLength(1);
    });

    it('does not request again while a lock is held or pending', async () => {
        const wakeLock = fakeWakeLock();
        const lock = createScreenWakeLock({ wakeLock, doc: fakeDocument() });

        lock.setWanted(true);
        lock.setWanted(true);
        await flush();
        lock.setWanted(true);
        await flush();

        expect(wakeLock.request).toHaveBeenCalledTimes(1);
    });

    it('releases the lock when no longer wanted', async () => {
        const wakeLock = fakeWakeLock();
        const lock = createScreenWakeLock({ wakeLock, doc: fakeDocument() });

        lock.setWanted(true);
        await flush();
        lock.setWanted(false);
        await flush();

        expect(wakeLock.held()).toHaveLength(0);
    });

    it('re-requests the lock when the page becomes visible again', async () => {
        const wakeLock = fakeWakeLock();
        const doc = fakeDocument();
        const lock = createScreenWakeLock({ wakeLock, doc });

        lock.setWanted(true);
        await flush();
        // The browser releases a screen wake lock when the page is hidden.
        doc.setVisibility('hidden');
        await wakeLock.sentinels[0].release();
        await flush();
        expect(wakeLock.request).toHaveBeenCalledTimes(1);

        doc.setVisibility('visible');
        await flush();

        expect(wakeLock.request).toHaveBeenCalledTimes(2);
        expect(wakeLock.held()).toHaveLength(1);
    });

    it('does not request on visibility change when not wanted', async () => {
        const wakeLock = fakeWakeLock();
        const doc = fakeDocument();
        createScreenWakeLock({ wakeLock, doc });

        doc.setVisibility('hidden');
        doc.setVisibility('visible');
        await flush();

        expect(wakeLock.request).not.toHaveBeenCalled();
    });

    it('waits for the page to be visible before requesting', async () => {
        const wakeLock = fakeWakeLock();
        const doc = fakeDocument('hidden');
        const lock = createScreenWakeLock({ wakeLock, doc });

        lock.setWanted(true);
        await flush();
        expect(wakeLock.request).not.toHaveBeenCalled();

        doc.setVisibility('visible');
        await flush();
        expect(wakeLock.request).toHaveBeenCalledTimes(1);
    });

    it('releases a lock that arrives after it stopped being wanted', async () => {
        const wakeLock = fakeWakeLock();
        wakeLock.deferNext = true;
        const lock = createScreenWakeLock({ wakeLock, doc: fakeDocument() });

        lock.setWanted(true);
        lock.setWanted(false);
        wakeLock.deferred.shift()();
        await flush();

        expect(wakeLock.held()).toHaveLength(0);
    });

    it('requests again after a rejected request once the page is visible again', async () => {
        const wakeLock = fakeWakeLock();
        wakeLock.rejectNext = new DOMException('denied', 'NotAllowedError');
        const doc = fakeDocument();
        const lock = createScreenWakeLock({ wakeLock, doc });

        lock.setWanted(true);
        await flush();
        expect(wakeLock.held()).toHaveLength(0);

        doc.setVisibility('hidden');
        doc.setVisibility('visible');
        await flush();

        expect(wakeLock.request).toHaveBeenCalledTimes(2);
        expect(wakeLock.held()).toHaveLength(1);
    });

    it('does nothing without wake lock support', async () => {
        const doc = fakeDocument();
        const lock = createScreenWakeLock({ wakeLock: undefined, doc });

        expect(() => {
            lock.setWanted(true);
            doc.setVisibility('hidden');
            doc.setVisibility('visible');
            lock.setWanted(false);
        }).not.toThrow();
        await flush();
    });

    it('does not throw when request throws synchronously', async () => {
        const wakeLock = fakeWakeLock();
        wakeLock.request.mockImplementationOnce(() => { throw new TypeError('not allowed'); });
        const lock = createScreenWakeLock({ wakeLock, doc: fakeDocument() });

        expect(() => lock.setWanted(true)).not.toThrow();
        await flush();
        expect(wakeLock.held()).toHaveLength(0);
    });
});
