// The session's pause (#163), registered as Alpine.store('pause'). The server
// owns it: handlers.js applies pause_update, pause_rejected and the pause in
// join_success; a display's settings panel sends pause_start / pause_end.
// The display counts down against the server clock (offsetMs from the server
// time in each message), so a display with a wrong clock shows the same time.
// The server also decides the end: at 0:00 the display waits for its update.

// How often the countdown refreshes. A display refresh, not a delay: nothing
// waits on it, and the end comes from the server.
export const PAUSE_TICK_MS = 250;
// Rejection codes with a text in the locales (pause.errors.*).
const REJECTION_CODES = ['past', 'too_long', 'invalid'];

// "9:41", or "1:05:00" from one hour on; rounds up like the lift timer.
export function formatPauseRemaining(ms) {
    const total = Math.max(0, Math.ceil(ms / 1000));
    const h = Math.floor(total / 3600);
    const m = Math.floor((total % 3600) / 60);
    const s = String(total % 60).padStart(2, '0');
    return h > 0 ? `${h}:${String(m).padStart(2, '0')}:${s}` : `${m}:${s}`;
}

export function createPauseStore({ now = () => Date.now() } = {}) {
    let ticker = null;

    return {
        pause: null,          // { endAtMs, mode: 'minutes' | 'until', until, nextLift } or null
        offsetMs: 0,          // server clock minus this device's clock
        remainingMs: 0,
        pending: false,       // this display sent pause_start / pause_end, no answer yet
        error: '',            // code of the last pause_rejected ('past', 'too_long', 'invalid')
        confirmedChanges: 0,  // bumped when the server answered this display's request

        get active() { return this.pause !== null; },

        remainingText() { return formatPauseRemaining(this.remainingMs); },

        // pause_update: the pause as the server sent it (null = none).
        apply(pause, serverNowMs) {
            if (serverNowMs != null) this.offsetMs = serverNowMs - now();
            this.pause = pause ? {
                endAtMs: pause.end_at_ms,
                mode: pause.mode,
                until: pause.until,
                nextLift: pause.next_lift,
            } : null;
            if (this.pending) {
                this.pending = false;
                this.confirmedChanges += 1;
            }
            this._tick();
            clearInterval(ticker);
            ticker = this.pause ? setInterval(() => this._tick(), PAUSE_TICK_MS) : null;
        },

        // join_success after a join, reload or reconnect: the server state is the
        // truth; a request still pending may or may not have arrived and is shown
        // through that state.
        joined(pause, serverNowMs) {
            this.pending = false;
            this.error = '';
            this.apply(pause, serverNowMs);
        },

        requestSent() {
            this.pending = true;
            this.error = '';
        },

        rejected(code) {
            this.pending = false;
            this.error = REJECTION_CODES.includes(code) ? code : 'invalid';
        },

        _tick() {
            this.remainingMs = this.pause ? Math.max(0, this.pause.endAtMs - (now() + this.offsetMs)) : 0;
        },
    };
}
