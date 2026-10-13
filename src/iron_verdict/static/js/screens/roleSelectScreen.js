// Role-select screen: session code and QR code, the four role buttons, the
// role-taken notice and (VPortal sessions) the VPortal connect button.

import { roleTakenNotice } from '../roleTakeover.js';

export function roleSelectScreen(conn) {
    return {
        init() {
            this.$watch('$store.nav.screen', (value) => {
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

        generateQrCode() {
            const el = this.$refs.qrcode;
            if (!el || !this.$store.session.code) return;
            while (el.firstChild) el.removeChild(el.firstChild);
            const url = window.location.origin + '/?session=' + this.$store.session.code;
            new QRCode(el, {
                text: url,
                width: 200,
                height: 200,
                colorDark: '#000000',
                colorLight: '#ffffff',
            });
        },
    };
}
