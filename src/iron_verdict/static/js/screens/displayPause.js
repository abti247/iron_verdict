// Pause of the session (#163), mixed into the display screen component: the
// pause form of the settings panel (minutes or a time of day, optional next
// lift type; "End pause") and what the pause shows. The pause itself is
// server state in Alpine.store('pause'); this file only holds the form and
// sends pause_start / pause_end through the connection.
//
// While a pause runs, the timer, lights, verdict and VPortal lifter are hidden
// and the pause shows big in the middle (paused()); not while editing the layout.

import { t } from '../i18n.js';

const pad = (n) => String(n).padStart(2, '0');

// End of today's "HH:MM" on this device's clock, in epoch ms; null if not a time.
export function endOfTimeToday(hhmm, now = new Date()) {
    const match = /^(\d{2}):(\d{2})$/.exec(hhmm || '');
    if (!match) return null;
    const end = new Date(now);
    end.setHours(Number(match[1]), Number(match[2]), 0, 0);
    return end.getTime();
}

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
            if (this.pauseMode === 'minutes') message.minutes = this.pauseMinutes;
            else message.end_at_ms = endOfTimeToday(this.pauseUntil);
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

        paused() {
            return this.$store.pause.active && !this.layoutEditing;
        },

        pauseTimeText() {
            const pause = this.$store.pause.pause;
            if (!pause) return '';
            if (pause.mode === 'until') {
                const end = new Date(pause.endAtMs);
                return t('pause.until').replace('{time}', `${pad(end.getHours())}:${pad(end.getMinutes())}`);
            }
            return t('pause.remaining').replace('{time}', this.$store.pause.remainingText());
        },

        pauseNextText() {
            const lift = this.$store.pause.pause?.nextLift;
            return lift ? t('pause.next').replace('{lift}', t(`liftTypes.${lift}`)) : '';
        },
    };
}
