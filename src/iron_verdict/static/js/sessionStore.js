// Session state shared by several screens, registered as Alpine.store('session'):
// which session this device is in, in which role, and how its connection stands.
// Data only — the join/leave flows that write it stay in app.js and handlers.js.
// Screen-local state (votes, timer, display phases) stays in ironVerdictApp.

export function createSessionStore() {
    return {
        code: '',
        name: '',
        kind: 'generic',  // 'generic' | 'vportal' — set at create/lookup, corrected on display start
        role: '',
        isHead: false,
        connectionStatus: 'disconnected',  // 'disconnected' | 'reconnecting' | 'connected'
        serverRestarting: false,
        judgeConnected: { left: false, center: false, right: false },
    };
}
