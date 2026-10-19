// Display screen: timer, vote lights with reasons and verdict, the VPortal lifter
// overlay, and the local settings panel (zoom and contrast mode, opened with
// the gear or "S"). What is shown comes from the display, timer and vportal
// stores; this component only holds the zoom, the contrast mode and whether the
// settings panel is open. Both settings are per device (localStorage).

const DISPLAY_ZOOM_KEY = 'iron-verdict:display-zoom';
const DISPLAY_CONTRAST_KEY = 'iron-verdict:display-contrast';

export function displayScreen(conn) {
    return {
        displaySettingsOpen: false,
        displayZoom: 1,
        displayContrast: false,
        _displayKeydownHandler: null,

        init() {
            this._loadDisplayZoomFromStorage();
            this._loadDisplayContrastFromStorage();
            this._installDisplayKeyHandler();
            // Any screen change closes the panel.
            this.$watch('$store.nav.screen', () => { this.displaySettingsOpen = false; });
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

        resetDisplayZoom() {
            this.displayZoom = 1;
            try { localStorage.setItem(DISPLAY_ZOOM_KEY, '1'); } catch (_) {}
        },

        onDisplayZoomInput(event) {
            const n = parseFloat(event.target.value);
            if (!Number.isFinite(n)) return;
            this.displayZoom = Math.min(1.5, Math.max(0.7, n));
            try { localStorage.setItem(DISPLAY_ZOOM_KEY, String(this.displayZoom)); } catch (_) {}
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

        _loadDisplayZoomFromStorage() {
            try {
                const raw = localStorage.getItem(DISPLAY_ZOOM_KEY);
                if (raw == null) return;
                const n = parseFloat(raw);
                if (!Number.isFinite(n)) return;
                this.displayZoom = Math.min(1.5, Math.max(0.7, n));
            } catch (_) {}
        },

        _installDisplayKeyHandler() {
            if (this._displayKeydownHandler) return;
            this._displayKeydownHandler = (e) => {
                if (this.$store.nav.screen !== 'display') return;
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
