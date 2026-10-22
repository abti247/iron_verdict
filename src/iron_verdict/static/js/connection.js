// The connection to the session: the one owner of the WebSocket. Joins a role,
// looks a session up, restores it after a reload, leaves it (to role-select or the
// landing screen) and dispatches every incoming message to handlers.js, which write
// the stores. Screen components only display stores and call these functions.
//
// Why one module, not a component: the socket belongs to no screen, so no screen
// can open a second one (see docs/architecture.md, WebSocket client), and every way
// out of the display passes here, so the VPortal display overlay is always stopped.
// Plain object with injectable dependencies, so the flows run under Vitest.

import { createWebSocket } from './websocket.js';
import { createRoleTakenTracker, failRoleTakenOver } from './roleTakeover.js';
import { restoreStoredSession, isReconnectCancelled, failReconnectSessionGone } from './reloadRecovery.js';
import { t as translate } from './i18n.js';
import {
    handleJoinSuccess,
    handleJoinError,
    handleError,
    handleShowResults,
    handleResetForNextLift,
    handleTimerStart,
    handleTimerReset,
    handleSessionEnded,
    handleSettingsUpdate,
    handleServerRestarting,
    handleJudgeStatusUpdate,
    handleVoteAck,
    handleVoteRejected,
    handlePauseUpdate,
    handlePauseRejected,
} from './handlers.js';

const DISPATCH = {
    ping:                (c) => c.send({ type: 'pong' }),
    join_success:        handleJoinSuccess,
    join_error:          handleJoinError,
    error:               handleError,
    show_results:        handleShowResults,
    reset_for_next_lift: handleResetForNextLift,
    timer_start:         handleTimerStart,
    timer_reset:         handleTimerReset,
    session_ended:       handleSessionEnded,
    settings_update:     handleSettingsUpdate,
    server_restarting:   handleServerRestarting,
    judge_status_update: handleJudgeStatusUpdate,
    vote_ack:            handleVoteAck,
    vote_rejected:       handleVoteRejected,
    pause_update:        handlePauseUpdate,
    pause_rejected:      handlePauseRejected,
};

// stores: { session, nav, judge, display, timer, settings, vportal, pause }.
export function createConnection({
    stores,
    storage = sessionStorage,
    location = window.location,
    openSocket = createWebSocket,
    fetchFn = (...args) => fetch(...args),
    t = translate,
    alert = (text) => window.alert(text),
    roleTaken = createRoleTakenTracker(),
}) {
    let ws = null;
    const { session, nav, judge, timer, vportal } = stores;

    // The demo flag is stored with the session so a reloaded demo window keeps showing "DEMO";
    // the VPortal kind so a reloaded device shows the VPortal button on role-select even
    // while the session lookup still fails (#175).
    const storedEntry = (entry) => ({
        ...entry,
        ...(session.isDemo ? { demo: true } : {}),
        ...(session.kind === 'vportal' ? { kind: 'vportal' } : {}),
    });

    // The server's kind corrects the stored one, if this session is still stored.
    const storeKind = (code) => {
        let entry;
        try { entry = JSON.parse(storage.getItem('iv_session')); } catch (_e) { return; }
        if (entry?.code !== code) return;
        delete entry.kind;
        if (session.kind === 'vportal') entry.kind = 'vportal';
        storage.setItem('iv_session', JSON.stringify(entry));
    };

    const startDisplayOverlay = (code) => {
        vportal.startDisplayOverlay(code, { streamOverlay: session.overlay }).then((kind) => {
            if (!kind) return;
            session.kind = kind;
            storeKind(code);
        }).catch((err) => console.warn('VPortal display overlay failed to start', err));
    };

    const c = {
        ...stores,
        storage,
        t,
        alert,
        roleTaken,

        send(data) {
            ws.send(data);
        },

        closeSocket() {
            if (ws) ws.close();
        },

        handleMessage(message) {
            const handler = DISPATCH[message.type];
            if (!handler) {
                console.warn('Ignoring unknown WebSocket message type:', message.type);
                return;
            }
            handler(c, message);
        },

        joinSession(role) {
            session.role = role;
            session.roleTakenOver = '';
            roleTaken.reset();
            const code = session.code || session.joinCode;
            session.code = code;
            const sessionEntry = storedEntry({ code, role });
            const existingSession = storage.getItem('iv_session');
            if (existingSession) {
                try {
                    const parsed = JSON.parse(existingSession);
                    if (parsed.code === code && parsed.role === role && parsed.reconnect_token) {
                        sessionEntry.reconnect_token = parsed.reconnect_token;
                    }
                } catch (_e) {}
            }
            storage.setItem('iv_session', JSON.stringify(sessionEntry));
            session.connectionStatus = 'reconnecting';

            const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
            const url = `${protocol}//${location.host}/ws`;

            const socket = openSocket(
                url,
                (message) => c.handleMessage(message),
                (error) => console.error('WebSocket error:', error),
                () => {},
                () => {
                    session.connectionStatus = 'connected';
                    session.serverRestarting = false;
                    let reconnectToken = null;
                    const stored = storage.getItem('iv_session');
                    if (stored) {
                        try { reconnectToken = JSON.parse(stored).reconnect_token || null; } catch (_e) {}
                    }
                    const joinMsg = { type: 'join', session_code: code, role: role };
                    if (reconnectToken) joinMsg.reconnect_token = reconnectToken;
                    socket.send(joinMsg);
                },
                () => { session.connectionStatus = 'reconnecting'; }
            );
            ws = socket;

            if (role === 'display') startDisplayOverlay(code);
        },

        // The VPortal login of this device changed while it shows the display (connect
        // dialog opened from the stream overlay's panel): poll with the new login, or stop.
        restartDisplayOverlay() {
            if (session.role !== 'display' || nav.screen !== 'display' || !session.code) return;
            if (session.overlayNotice) return;  // stream overlay without a session
            startDisplayOverlay(session.code);
        },

        // Look up the code typed on the landing screen (or restored after a reload) and
        // go to role-select if the session exists.
        async lookupSession() {
            const code = session.joinCode.trim().toUpperCase();
            if (code.length !== 8 || session.joinChecking) return;
            session.joinChecking = true;
            session.joinError = '';
            const restoring = nav.screen === 'reconnecting';
            try {
                const res = await fetchFn('/api/sessions/' + code);
                // Reload recovery cancelled while the lookup was running — the user left on purpose.
                if (isReconnectCancelled(c, restoring)) return;
                if (res.ok) {
                    session.code = code;
                    session.joinCode = code;
                    try {
                        const data = await res.json();
                        session.kind = data.kind || 'generic';
                        vportal.applySessionInfo(code, data);
                    } catch (_e) {
                        session.kind = 'generic';
                        vportal.applySessionInfo(code, null);
                    }
                    storage.setItem('iv_session', JSON.stringify(storedEntry({ code })));
                    nav.navigateTo('role-select');
                } else if (res.status === 404 || res.status === 422) {
                    if (nav.screen === 'reconnecting') {
                        failReconnectSessionGone(c);
                        return;
                    }
                    storage.removeItem('iv_session');
                    session.joinError = t('landing.sessionNotFound');
                } else {
                    nav.navigateTo('landing');
                    session.joinError = t('landing.lookupFailed');
                }
            } catch (_e) {
                if (isReconnectCancelled(c, restoring)) return;
                nav.navigateTo('landing');
                session.joinError = t('landing.lookupFailed');
            } finally {
                session.joinChecking = false;
            }
        },

        returnToLanding() {
            storage.removeItem('iv_session');
            vportal.stopDisplayOverlay();
            judge.clearPendingVote();
            c.closeSocket();
            nav.navigateTo('landing');
            session.code = '';
            session.joinCode = '';
            session.isDemo = false;
            session.name = '';
            session.newSessionName = '';
            session.joinError = '';
            session.roleTakenOver = '';
        },

        returnToRoleSelection() {
            vportal.stopDisplayOverlay();
            // Downgrade to a code-only entry so a reload on role-select returns here.
            if (session.code) {
                storage.setItem('iv_session', JSON.stringify(storedEntry({ code: session.code })));
            } else {
                storage.removeItem('iv_session');
            }
            c.closeSocket();
            nav.navigateTo('role-select');
            judge.resetVoting();
            timer.reset();
        },

        // Stream overlay (OBS browser source): joins as display without a click and
        // never leaves the display screen — no landing, role-select or "Connecting…"
        // screen, no history entry. The URL stays as it is, so a reload (OBS reloads
        // browser sources now and then) starts the overlay again.
        startOverlay({ code, layoutCode = '' }) {
            const trimmed = String(code || '').trim().toUpperCase();
            session.overlay = true;
            session.overlayLayoutCode = layoutCode || '';
            session.overlayNotice = '';
            nav.screen = 'display';
            if (trimmed.length !== 8) {
                session.overlayNotice = t('overlay.sessionNotFound');
                return;
            }
            session.code = trimmed;
            session.joinCode = trimmed;
            c.joinSession('display');
        },

        // The overlay lost its session (ended, not found, join refused): the socket is
        // already closed and the VPortal overlay stopped; show why, without an alert
        // (it would block the OBS browser source) and without leaving the display.
        failOverlay(notice) {
            storage.removeItem('iv_session');
            stores.display.clear();
            timer.reset();
            session.overlayNotice = notice;
        },

        cancelReconnect() {
            c.returnToLanding();
        },

        failReconnectSessionGone() {
            failReconnectSessionGone(c);
        },

        failRoleTakenOver() {
            failRoleTakenOver(c);
        },

        // The browser's back/forward button moved to `target` (the screen in history.state).
        followHistory(target) {
            nav.handlingPopstate = true;
            try {
                if (target === 'role-select') {
                    c.returnToRoleSelection();
                } else if (target === 'landing') {
                    c.returnToLanding();
                } else {
                    nav.screen = target;
                }
            } finally {
                nav.handlingPopstate = false;
            }
        },

        // Head judge only: send the current settings to every client of the session.
        sendSettings() {
            if (!session.isHead) return;
            if (ws && ws.readyState === WebSocket.OPEN) {
                c.send({
                    type: 'settings_update',
                    showExplanations: stores.settings.showExplanations,
                    liftType: stores.settings.liftType,
                    requireReasons: stores.settings.requireReasons,
                });
            }
        },

        // First screen after Alpine started: the stream overlay (?session=…&overlay=1),
        // a QR-code link (?session=…), a session stored before a reload, a demo window
        // (?code=…&demo=<role>) or the landing screen.
        start({ urlSession = null, overlayParams = null, demoParams = null } = {}) {
            if (overlayParams) {
                c.startOverlay(overlayParams);
                return;
            }

            if (urlSession) {
                const trimmed = urlSession.trim().toUpperCase();
                session.joinCode = trimmed;
                nav.screen = 'landing';
                if (trimmed.length === 8) {
                    // Deferred so the screen components have initialised first.
                    setTimeout(() => c.lookupSession(), 0);
                } else if (trimmed.length > 0) {
                    session.joinError = t('landing.sessionNotFound');
                }
                return;
            }

            // Reload recovery: rejoin the previous session or return to role-select (reloadRecovery.js).
            if (restoreStoredSession(c)) return;

            if (demoParams) {
                session.code = demoParams.code;
                session.joinCode = demoParams.code;
                session.isDemo = true;
                // Unchanged from before the split: the demo window joins shortly after start.
                setTimeout(() => c.joinSession(demoParams.demo), 100);
            } else {
                nav.screen = 'landing';
            }
        },
    };
    return c;
}
