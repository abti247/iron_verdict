// Keeps the device's screen on while the judge or display screen is showing
// (Screen Wake Lock API, #235). A locked judge phone loses its WebSocket (iOS)
// and its vote can miss the result; a sleeping display laptop shows nothing.
//
// The browser releases the lock whenever the page is hidden (tab switch, phone
// locked by hand), so it is requested again each time the page becomes visible.
// Without support (older browser, or plain http:// on venue Wi-Fi: the API
// needs a secure context) or when the browser refuses, nothing happens — no
// error, no notice, no delay; the competition checklist covers those devices.

const WAKE_SCREENS = new Set(['judge', 'display']);

export function keepsScreenAwake(screen) {
    return WAKE_SCREENS.has(screen);
}

export function createScreenWakeLock({
    wakeLock = globalThis.navigator?.wakeLock,
    doc = globalThis.document,
} = {}) {
    const supported = !!wakeLock && typeof wakeLock.request === 'function';
    let wanted = false;
    let sentinel = null;   // the held lock, null once released
    let requesting = false;

    function acquire() {
        if (!supported || !wanted || sentinel || requesting) return;
        if (doc && doc.visibilityState !== 'visible') return;
        requesting = true;
        let request;
        try {
            request = Promise.resolve(wakeLock.request('screen'));
        } catch (_) {
            requesting = false;
            return;
        }
        request.then((lock) => {
            requesting = false;
            if (!wanted) {
                // The screen changed while the request was pending.
                lock.release().catch(() => {});
                return;
            }
            sentinel = lock;
            lock.addEventListener('release', () => {
                if (sentinel === lock) sentinel = null;
            });
        }, () => {
            // Refused (e.g. page hidden, battery saver): retried on the next
            // visibility change, never in a loop.
            requesting = false;
        });
    }

    function release() {
        const lock = sentinel;
        sentinel = null;
        if (lock) lock.release().catch(() => {});
    }

    if (supported && doc) {
        doc.addEventListener('visibilitychange', () => {
            if (doc.visibilityState === 'visible') acquire();
        });
    }

    return {
        setWanted(on) {
            wanted = !!on;
            if (wanted) acquire();
            else release();
        },
    };
}
