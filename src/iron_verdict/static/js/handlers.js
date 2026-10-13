// One named handler per incoming WebSocket message type, dispatched by
// connection.js. `c` is the connection: the stores (session, nav, judge, display,
// timer, settings, vportal) plus its flows, storage, t and alert.

import { rejectionKey } from './voteDelivery.js';

function translateReasons(c, rawReasons) {
    return {
        left: rawReasons.left ? c.t(rawReasons.left) : null,
        center: rawReasons.center ? c.t(rawReasons.center) : null,
        right: rawReasons.right ? c.t(rawReasons.right) : null,
    };
}

export function handleJoinSuccess(c, message) {
    const session = c.session;
    session.isHead = message.is_head;
    c.roleTaken.reset();
    session.name = message.session_state?.name || '';
    c.nav.navigateTo(session.role === 'display' ? 'display' : 'judge');

    // Initialize live connectivity state from session snapshot
    const judges = message.session_state?.judges;
    if (judges) {
        session.judgeConnected = {
            left: judges.left?.connected ?? false,
            center: judges.center?.connected ?? false,
            right: judges.right?.connected ?? false,
        };
    }

    c.judge.liftId = message.session_state?.lift_id ?? null;

    // Reconcile this judge's vote with the server: confirmed, resend pending, or open
    if (session.role && session.role.endsWith('_judge')) {
        const position = session.role.replace('_judge', '');
        c.judge.reconcileVoteAfterJoin(judges?.[position]);
    }

    // Persist reconnect token for future reconnections
    if (message.reconnect_token) {
        const stored = c.storage.getItem('iv_session');
        if (stored) {
            try {
                const parsed = JSON.parse(stored);
                parsed.reconnect_token = message.reconnect_token;
                c.storage.setItem('iv_session', JSON.stringify(parsed));
            } catch (_e) {}
        }
    }

    // Server state is always authoritative — restoring from localStorage could bleed
    // settings from a previous session (e.g. deadlift cached into a new squat session).
    const settings = message.session_state?.settings;
    if (settings) {
        if (settings.lift_type !== undefined) c.settings.liftType = settings.lift_type;
        if (settings.show_explanations !== undefined) c.settings.showExplanations = settings.show_explanations;
        if (settings.require_reasons !== undefined) c.settings.requireReasons = settings.require_reasons;
    }
    if (session.isHead) {
        // Broadcast the server-restored settings to all currently connected clients.
        c.sendSettings();
    }
    const trms = message.session_state?.time_remaining_ms;
    if (trms > 0) {
        c.timer.start(trms);
    }
}

export function handleJoinError(c, message) {
    if (message.message === 'Role already taken') {
        // With a stored reconnect token the rejection may be a short race during
        // reconnection: retry silently until the give-up limit, then the position counts
        // as taken by another device (roleTakeover.js). A new user with no token must
        // see the error.
        let hasReconnectToken = false;
        const stored = c.storage.getItem('iv_session');
        if (stored) {
            try { hasReconnectToken = !!JSON.parse(stored).reconnect_token; } catch (_e) {}
        }
        if (hasReconnectToken) {
            if (c.roleTaken.rejectedShouldGiveUp()) c.failRoleTakenOver();
            return;
        }
    }
    if (c.nav.screen === 'reconnecting' && message.message === 'Session not found') {
        c.failReconnectSessionGone();
        return;
    }
    c.closeSocket();
    c.vportal.stopDisplayOverlay();
    c.storage.removeItem('iv_session');
    const sanitizedMessage = document.createTextNode(message.message).textContent;
    c.alert(`${c.t('alerts.joinFailed')} ${sanitizedMessage}`);
    // A failed reload recovery must not leave the page on "Connecting…".
    if (c.nav.screen === 'reconnecting') c.returnToLanding();
}

export function handleError(c, message) {
    const sanitizedMessage = document.createTextNode(message.message).textContent;
    c.alert(`${c.t('alerts.error')} ${sanitizedMessage}`);
}

export function handleShowResults(c, message) {
    c.timer.freeze(message.timer_frozen_ms);
    const rawReasons = message.reasons || { left: null, center: null, right: null };
    c.judge.showResults(message.votes, translateReasons(c, rawReasons));
    if (c.session.role === 'display') {
        c.display.showResults({
            votes: message.votes,
            reasons: translateReasons(c, rawReasons),
            showExplanations: message.showExplanations,
            liftType: message.liftType,
        });
    }
}

export function handleResetForNextLift(c, message) {
    const voteWasSending = c.judge.voteState === 'sending';
    c.judge.resetVoting();
    if (message.lift_id != null) c.judge.liftId = message.lift_id;
    // A vote still unconfirmed when the lift ends may or may not have counted — tell the judge the lift moved on.
    if (voteWasSending) c.judge.voteError = rejectionKey('lift_changed');
    c.timer.reset();
    if (c.session.role === 'display') {
        c.display.clear();
    }
}

export function handleTimerStart(c, message) {
    c.timer.start(message.time_remaining_ms);
}

export function handleTimerReset(c, _message) {
    c.timer.reset();
}

export function handleSessionEnded(c, _message) {
    c.judge.clearPendingVote();
    c.vportal.stopDisplayOverlay();
    c.alert(c.t('alerts.sessionEnded'));
    c.closeSocket();
    c.session.isDemo = false;
    c.storage.removeItem('iv_session');
    c.nav.navigateTo('landing');
}

export function handleSettingsUpdate(c, message) {
    if (message.showExplanations !== undefined) {
        c.settings.showExplanations = message.showExplanations;
    }
    if (message.liftType !== undefined) {
        c.settings.liftType = message.liftType;
    }
    if (message.requireReasons !== undefined) {
        c.settings.requireReasons = message.requireReasons;
    }
}

export function handleServerRestarting(c, _message) {
    c.session.serverRestarting = true;
}

export function handleJudgeStatusUpdate(c, message) {
    c.session.judgeConnected[message.position] = message.connected;
}

export function handleVoteAck(c, message) {
    c.judge.applyVoteAck(message);
}

export function handleVoteRejected(c, message) {
    c.judge.applyVoteRejected(message);
}
