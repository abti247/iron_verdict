// Lights view of the stream overlay (#215), mixed into the display screen
// component: BVDK view (default) or Iron Verdict Classic, chosen in the
// overlay's panel and kept on this device (bvdkLights.js). The BVDK box sits
// in the layout's "Lights" block, so both views share the overlay layout.
//
// The box shows only with a result; while the layout is edited without one it
// shows a sample to place it (faded, labelled). When the next lift clears the
// result, the box fades out with the result it showed (bvdkView() keeps the
// last one), so the fade never shows an emptied box.

import { bvdkResult, loadLightsView, saveLightsView } from '../bvdkLights.js';
import { t } from '../i18n.js';

// null when the browser blocks site data; load/save then fall back or report it.
function storage() {
    try { return window.localStorage; } catch (_) { return null; }
}

function sampleResult(liftType) {
    return bvdkResult({
        votes: { left: 'white', center: 'yellow', right: 'blue' },
        reasons: {
            left: null,
            center: t('reasons.squat.yellow.supportingContactOnLegs'),
            right: t('reasons.squat.blue.softKnees'),
        },
        showExplanations: true,
        liftType,
    });
}

export function displayBvdk() {
    // Not reactive on purpose: written while rendering, read only during the fade.
    let lastShown = null;
    return {
        overlayLightsView: 'bvdk',        // 'bvdk' | 'classic'
        overlayLightsSaveError: false,    // the choice could not be stored on this device

        initDisplayBvdk() {
            this.overlayLightsView = loadLightsView(storage());
        },

        setOverlayLightsView(view) {
            this.overlayLightsView = view;
            this.overlayLightsSaveError = !saveLightsView(storage(), view);
        },

        bvdkActive() {
            return this.$store.session.overlay && this.overlayLightsView === 'bvdk';
        },

        bvdkIsSample() {
            return this.layoutEditing && this.$store.display.phase !== 'votes';
        },

        bvdkShown() {
            return this.$store.display.phase === 'votes' || this.layoutEditing;
        },

        bvdkView() {
            const display = this.$store.display;
            if (display.phase === 'votes') {
                lastShown = bvdkResult(display);
                return lastShown;
            }
            if (this.layoutEditing || !lastShown) return sampleResult(display.liftType);
            return lastShown;
        },
    };
}
