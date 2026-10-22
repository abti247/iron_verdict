// Session state shared by several screens, registered as Alpine.store('session'):
// which session this device is in, in which role, how its connection stands, and
// the landing form that picks the session. Data only — connection.js and the
// landing screen write it.

export function createSessionStore() {
    return {
        code: '',
        name: '',
        kind: 'generic',  // 'generic' | 'vportal' — set at create/lookup/reload (stored in iv_session), corrected on display start
        role: '',
        isHead: false,
        isDemo: false,  // joined from a demo window (?code=…&demo=<role>)
        overlay: false,  // stream overlay for OBS (?session=…&overlay=1): a display without controls
        overlayLayoutCode: '',  // layout export code from the overlay URL (&layout=…); '' = none
        overlayNotice: '',  // why the overlay shows no session (ended, not found, join failed)
        connectionStatus: 'disconnected',  // 'disconnected' | 'reconnecting' | 'connected'
        serverRestarting: false,
        judgeConnected: { left: false, center: false, right: false },
        roleTakenOver: '',  // role whose position another device took; shows the role-select notice
        // Landing form. Kept here, not in the landing component: the landing screen is
        // removed from the DOM when left, and reload recovery and the leave flows write it.
        newSessionName: '',
        joinCode: '',
        joinError: '',
        joinChecking: false,
    };
}
