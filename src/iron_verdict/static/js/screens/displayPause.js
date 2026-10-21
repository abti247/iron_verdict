// Pause of the session (#163), mixed into the display screen component: the
// pause form of the settings panel (minutes or a time of day, optional next
// lift type; "End pause") and what the pause block shows. The pause itself is
// server state in Alpine.store('pause'); this file only holds the form and
// sends pause_start / pause_end through the connection.
//
// While a pause runs, the timer, lights, verdict and VPortal lifter are hidden
// (paused()); in the layout editor every block shows, the pause block with a
// sample if no pause runs, so all of them can be placed.

import { t } from '../i18n.js';
import { formatPauseRemaining } from '../pauseStore.js';

const SAMPLE_PAUSE = { mode: 'minutes', until: null, nextLift: 'bench' };
const SAMPLE_REMAINING_MS = 10 * 60 * 1000;

export function displayPause(conn) {
    return {
        pauseMode: 'minutes',   // 'minutes' | 'until'
        pauseMinutes: 10,
        pauseUntil: '',
        pauseNextLift: '',      // '' = none

        initDisplayPause() {
            // The server confirmed this display's start or end: close the panel,
            // so the hall sees the pause (or what follows it) without it.
            this.$watch('$store.pause.confirmedChanges', () => { this.displaySettingsOpen = false; });
        },

        // Only with an open connection: a message sent without one would be lost.
        pauseCanSend() {
            return this.$store.session.connectionStatus === 'connected' && !this.$store.pause.pending;
        },

        // The server checks the input and answers pause_update or pause_rejected.
        startPause() {
            if (!this.pauseCanSend()) return;
            const message = { type: 'pause_start', next_lift: this.pauseNextLift || null };
            if (this.pauseMode === 'minutes') {
                message.minutes = this.pauseMinutes;
            } else {
                message.until = this.pauseUntil;
                // The server computes the end with its own clock in this device's time zone.
                message.utc_offset_min = -new Date().getTimezoneOffset();
            }
            this.$store.pause.requestSent();
            conn.send(message);
        },

        endPause() {
            if (!this.pauseCanSend()) return;
            this.$store.pause.requestSent();
            conn.send({ type: 'pause_end' });
        },

        pauseErrorText() {
            const code = this.$store.pause.error;
            return code ? t(`pause.errors.${code}`) : '';
        },

        // A running pause hides the lift blocks; never while editing the layout.
        paused() {
            return this.$store.pause.active && !this.layoutEditing;
        },

        pauseBlockShown() {
            if (this.layoutEditing) return true;
            return this.$store.pause.active && !this.layoutBlockHidden('pause');
        },

        pauseIsSample() {
            return this.layoutEditing && !this.$store.pause.active;
        },

        _pauseView() {
            return this.$store.pause.pause || (this.layoutEditing ? SAMPLE_PAUSE : null);
        },

        pauseTimeText() {
            const pause = this._pauseView();
            if (!pause) return '';
            if (pause.mode === 'until') return t('pause.until').replace('{time}', pause.until);
            const remaining = this.$store.pause.active ? this.$store.pause.remainingText() : formatPauseRemaining(SAMPLE_REMAINING_MS);
            return t('pause.remaining').replace('{time}', remaining);
        },

        pauseNextText() {
            const lift = this._pauseView()?.nextLift;
            return lift ? t('pause.next').replace('{lift}', t(`liftTypes.${lift}`)) : '';
        },
    };
}
