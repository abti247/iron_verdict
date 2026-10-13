// Landing screen: create a session, look one up by code, or open the demo,
// contact or privacy screen. The form fields live in the session store.

export function landingScreen(conn) {
    return {
        async createSession() {
            const session = this.$store.session;
            try {
                session.kind = this.$store.nav.entryPath === '/vportal' ? 'vportal' : 'generic';
                const response = await fetch('/api/sessions', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        name: session.newSessionName.trim(),
                        kind: session.kind,
                    })
                });
                if (!response.ok) {
                    alert(t('alerts.createFailed'));
                    return;
                }
                const data = await response.json();
                session.code = data.session_code;
                session.name = session.newSessionName.trim();
                await this.$store.vportal.loadStagingFlag(session.code);
                sessionStorage.setItem('iv_session', JSON.stringify({ code: session.code }));
                this.$store.nav.navigateTo('role-select');
            } catch (error) {
                alert(t('alerts.createError'));
                console.error('Session creation error:', error);
            }
        },

        joinExistingSession() {
            conn.lookupSession();
        },
    };
}
