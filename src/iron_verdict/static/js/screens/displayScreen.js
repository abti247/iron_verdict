// Display screen: timer, vote lights with reasons and verdict, the VPortal lifter
// overlay, and the local settings panel (contrast mode and the layout editor,
// opened with the gear or "S"). What is shown comes from the display, timer and
// vportal stores; this component only holds the contrast mode, the layout
// (displayLayoutEditor.js) and whether the settings panel is open. Both
// settings are per device (localStorage).
//
// As stream overlay (session.overlay, OBS browser source) the same screen runs
// on a transparent page without gear or session name (display-overlay.css);
// "S" still opens the panel, which then also offers the VPortal connect dialog,
// because the overlay never passes role-select.

import { displayLayoutEditor } from './displayLayoutEditor.js';

const DISPLAY_CONTRAST_KEY = 'iron-verdict:display-contrast';

export function displayScreen(conn) {
    return {
        ...displayLayoutEditor(),
        displaySettingsOpen: false,
        displayContrast: false,
        _displayKeydownHandler: null,

        init() {
            this._loadDisplayContrastFromStorage();
            this.initDisplayLayout();
            this._installDisplayKeyHandler();
            // Any screen change closes the panel.
            this.$watch('$store.nav.screen', () => { this.displaySettingsOpen = false; });
            // Connected or disconnected in the dialog while on the display: poll with the new login.
            this.$watch('$store.vportal.loginChanges', () => conn.restartDisplayOverlay());
        },

        openVportalDialog() {
            this.displaySettingsOpen = false;
            this.$store.vportal.openModal();
        },

        returnToRoleSelection() {
            conn.returnToRoleSelection();
        },

        openDisplaySettings() {
            this.displaySettingsOpen = true;
        },

        closeDisplaySettings() {
            this.displaySettingsOpen = false;
        },

        toggleDisplayContrast() {
            this.displayContrast = !this.displayContrast;
            try { localStorage.setItem(DISPLAY_CONTRAST_KEY, this.displayContrast ? '1' : '0'); } catch (_) {}
        },

        _loadDisplayContrastFromStorage() {
            try {
                this.displayContrast = localStorage.getItem(DISPLAY_CONTRAST_KEY) === '1';
            } catch (_) {}
        },

        _installDisplayKeyHandler() {
            if (this._displayKeydownHandler) return;
            this._displayKeydownHandler = (e) => {
                if (this.$store.nav.screen !== 'display') return;
                // Only the editor's buttons end the edit mode, so a stray key
                // never drops or saves a layout.
                if (this.layoutEditing) return;
                const tag = (e.target && e.target.tagName) || '';
                if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
                if (e.key === 's' || e.key === 'S') {
                    e.preventDefault();
                    this.displaySettingsOpen = !this.displaySettingsOpen;
                } else if (e.key === 'Escape' && this.displaySettingsOpen) {
                    e.preventDefault();
                    this.displaySettingsOpen = false;
                }
            };
            window.addEventListener('keydown', this._displayKeydownHandler);
        },
    };
}
