// Stream overlay lights only after the decision (#216), mixed into the display
// screen component. Without a result the lights (with cards, reasons and
// verdict, in both lights views) are invisible in the stream; a live result
// shows them for the duration chosen in the overlay's panel (streamLights.js),
// then they fade out. The next lift and the start of a pause hide them
// earlier. "Always" keeps the hall display's behaviour. A result restored
// after a reload or reconnect is not shown again (displayStore.js). The hall
// display and the layout editor always show them.

import { loadLightsDuration, saveLightsDuration, LIGHTS_DURATIONS } from '../streamLights.js';

// null when the browser blocks site data; load/save then fall back or report it.
function storage() {
    try { return window.localStorage; } catch (_) { return null; }
}

export function displayStreamLights() {
    let hideTimer = null;
    return {
        overlayLightsDurations: LIGHTS_DURATIONS,
        overlayLightsDuration: 5,             // 'always' | seconds
        overlayLightsDurationSaveError: false,

        initDisplayStreamLights() {
            this.overlayLightsDuration = loadLightsDuration(storage());
            this.$watch('$store.display.liveResults', () => this._startStreamLightsDuration());
            this.$watch('$store.pause.active', (active) => {
                if (!active) return;
                clearTimeout(hideTimer);
                this.$store.display.hideFromStream();
            });
        },

        setOverlayLightsDuration(value) {
            const duration = value === 'always' ? 'always' : Number(value);
            this.overlayLightsDuration = duration;
            this.overlayLightsDurationSaveError = !saveLightsDuration(storage(), duration);
        },

        // A new live result: (re)start its time in the stream. A deliberate wait,
        // not a delay: it is the display time the maintainer asked for in the
        // stream and delays nothing of the judging (#216). A duration changed
        // meanwhile applies from the next result.
        _startStreamLightsDuration() {
            clearTimeout(hideTimer);
            if (this.overlayLightsDuration === 'always') return;
            const display = this.$store.display;
            hideTimer = setTimeout(() => display.hideFromStream(), this.overlayLightsDuration * 1000);
        },

        streamLightsVisible() {
            if (!this.$store.session.overlay || this.layoutEditing) return true;
            if (this.overlayLightsDuration === 'always') return true;
            return this.$store.display.phase === 'votes' && this.$store.display.streamShown;
        },

        // Classes of the Classic lights and the verdict in the overlay
        // (display-overlay.css). The fade only while a result is still there:
        // after the next lift the emptied lights must not fade out.
        streamLightsClass() {
            if (!this.$store.session.overlay) return '';
            if (this.streamLightsVisible()) return 'stream-lights-on';
            return this.$store.display.phase === 'votes' ? 'stream-lights-hide stream-lights-fade' : 'stream-lights-hide';
        },
    };
}
