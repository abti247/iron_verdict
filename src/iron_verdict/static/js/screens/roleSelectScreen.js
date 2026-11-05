// Role-select screen: session code (a link for a new tab) and QR code, the four role buttons, the
// role-taken notice, (VPortal sessions) the VPortal connect button and the
// stream-overlay URL for OBS to copy with its "?" explaining the OBS setup.

import { roleTakenNotice } from '../roleTakeover.js';

export function roleSelectScreen(conn) {
    return {
        overlayLinkOpen: false,
        overlayLinkCopied: false,
        overlayHelpOpen: false,

        init() {
            this.$watch('$store.nav.screen', (value) => {
                this.overlayLinkOpen = false;
                this.overlayLinkCopied = false;
                this.overlayHelpOpen = false;
                if (value === 'role-select' && this.$store.session.code) {
                    // Delay kept unchanged from before the split (app.js): lets x-show reveal
                    // the screen before the QR code is drawn.
                    setTimeout(() => this.generateQrCode(), 50);
                }
            });
        },

        joinSession(role) {
            conn.joinSession(role);
        },

        returnToLanding() {
            conn.returnToLanding();
        },

        // Rendered on each language change, so the notice follows the language toggle.
        roleTakenOverNotice() {
            const role = this.$store.session.roleTakenOver;
            return role ? roleTakenNotice(t, role) : '';
        },

        // Role select of this session — the URL of the QR code and of the session-code link.
        sessionUrl() {
            return window.location.origin + '/?session=' + this.$store.session.code;
        },

        // A plain click on the session code does nothing (#212): only Ctrl/Cmd+click,
        // middle click (auxclick, never reaches here) and the context menu open the link.
        onCodeClick(event) {
            if (!event.ctrlKey && !event.metaKey) event.preventDefault();
        },

        // Opens the display of this session as stream overlay, without a click (#107).
        overlayUrl() {
            return window.location.origin + '/?session=' + this.$store.session.code + '&overlay=1';
        },

        toggleOverlayLink() {
            this.overlayLinkOpen = !this.overlayLinkOpen;
            this.overlayLinkCopied = false;
        },

        // The clipboard API needs HTTPS; without it (or when refused) the URL is
        // selected, so Ctrl+C copies it.
        copyOverlayUrl() {
            const select = () => { this.$refs.overlayUrl.focus(); this.$refs.overlayUrl.select(); };
            const clipboard = navigator.clipboard;
            if (!clipboard || !window.isSecureContext) { select(); return; }
            clipboard.writeText(this.overlayUrl())
                .then(() => { this.overlayLinkCopied = true; })
                .catch(select);
        },

        generateQrCode() {
            const el = this.$refs.qrcode;
            if (!el || !this.$store.session.code) return;
            while (el.firstChild) el.removeChild(el.firstChild);
            new QRCode(el, {
                text: this.sessionUrl(),
                width: 200,
                height: 200,
                colorDark: '#000000',
                colorLight: '#ffffff',
            });
        },
    };
}
