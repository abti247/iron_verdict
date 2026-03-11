import { stopTimer } from './timer.js';

export function handleJoinSuccess(app, message) {
    app.isHead = message.is_head;
    app.sessionName = message.session_state?.name || '';
    app.screen = app.role === 'display' ? 'display' : 'judge';

    // Initialize live connectivity state from session snapshot
    const judges = message.session_state?.judges;
    if (judges) {
        app.judgeConnected = {
            left: judges.left?.connected ?? false,
            center: judges.center?.connected ?? false,
            right: judges.right?.connected ?? false,
        };
    }

    // Restore this judge's vote state if they were already locked before reconnecting
    if (app.role && app.role.endsWith('_judge')) {
        const position = app.role.replace('_judge', '');
        const myState = judges?.[position];
        if (myState?.locked) {
            app.voteLocked = true;
            app.selectedVote = myState.current_vote;
            app.selectedReason = myState.current_reason ?? null;
        }
    }

    // Persist reconnect token for future reconnections
    if (message.reconnect_token) {
        const stored = sessionStorage.getItem('iv_session');
        if (stored) {
            try {
                const parsed = JSON.parse(stored);
                parsed.reconnect_token = message.reconnect_token;
                sessionStorage.setItem('iv_session', JSON.stringify(parsed));
            } catch (_e) {}
        }
    }

    // Server state is always authoritative — restoring from localStorage could bleed
    // settings from a previous session (e.g. deadlift cached into a new squat session).
    const settings = message.session_state?.settings;
    if (settings) {
        if (settings.lift_type !== undefined) app.liftType = settings.lift_type;
        if (settings.show_explanations !== undefined) app.showExplanations = settings.show_explanations;
        if (settings.require_reasons !== undefined) app.requireReasons = settings.require_reasons;
    }
    if (app.isHead) {
        // Broadcast the server-restored settings to all currently connected clients.
        app.saveSettings();
    }
    const trms = message.session_state?.time_remaining_ms;
    if (trms > 0) {
        app.startTimerCountdown(trms);
    }
}

export function handleJoinError(app, message) {
    if (message.message === 'Role already taken') {
        // Only suppress if we have a stored reconnect token — this is a transient race
        // during reconnection (the server will accept the retry with the matching token).
        // A new user with no token must see the error.
        let hasReconnectToken = false;
        const stored = sessionStorage.getItem('iv_session');
        if (stored) {
            try { hasReconnectToken = !!JSON.parse(stored).reconnect_token; } catch (_e) {}
        }
        if (hasReconnectToken) return;
    }
    app.ws.close();
    sessionStorage.removeItem('iv_session');
    const sanitizedMessage = document.createTextNode(message.message).textContent;
    alert(`${t('alerts.joinFailed')} ${sanitizedMessage}`);
}

export function handleError(app, message) {
    const sanitizedMessage = document.createTextNode(message.message).textContent;
    alert(`${t('alerts.error')} ${sanitizedMessage}`);
}

export function handleShowResults(app, message) {
    app.resultsShown = true;
    stopTimer();
    if (message.timer_frozen_ms != null) {
        app.timerDisplay = String(Math.ceil(message.timer_frozen_ms / 1000));
    }
    app.judgeResultVotes = message.votes;
    const rawReasons = message.reasons || { left: null, center: null, right: null };
    app.judgeResultReasons = {
        left: rawReasons.left ? t(rawReasons.left) : null,
        center: rawReasons.center ? t(rawReasons.center) : null,
        right: rawReasons.right ? t(rawReasons.right) : null,
    };
    if (app.role === 'display') {
        clearTimeout(app._phaseTimer1);
        app.displayVotes = app.judgeResultVotes;
        app.displayReasons = {
            left: rawReasons.left ? t(rawReasons.left) : null,
            center: rawReasons.center ? t(rawReasons.center) : null,
            right: rawReasons.right ? t(rawReasons.right) : null,
        };
        app.displayShowExplanations = message.showExplanations;
        app.displayLiftType = message.liftType;
        app.displayPhase = 'votes';
        app.displayStatus = '';
    }
}

export function handleResetForNextLift(app, message) {
    clearTimeout(app._phaseTimer1);
    app.resetVoting();
    stopTimer();
    app.timerDisplay = '60';
    app.timerExpired = false;
    if (app.role === 'display') {
        app.displayVotes = { left: null, center: null, right: null };
        app.displayReasons = { left: null, center: null, right: null };
        app.displayPhase = 'idle';
        app.displayStatus = '';
    }
}

export function handleTimerStart(app, message) {
    app.startTimerCountdown(message.time_remaining_ms);
}

export function handleTimerReset(app, message) {
    stopTimer();
    app.timerDisplay = '60';
    app.timerExpired = false;
}

export function handleSessionEnded(app, message) {
    alert(t('alerts.sessionEnded'));
    app.ws.close();
    app.isDemo = false;
    sessionStorage.removeItem('iv_session');
    app.screen = 'landing';
}

export function handleSettingsUpdate(app, message) {
    if (message.showExplanations !== undefined) {
        app.showExplanations = message.showExplanations;
    }
    if (message.liftType !== undefined) {
        app.liftType = message.liftType;
    }
    if (message.requireReasons !== undefined) {
        app.requireReasons = message.requireReasons;
    }
}

export function handleServerRestarting(app, _message) {
    app.serverRestarting = true;
}

export function handleJudgeStatusUpdate(app, message) {
    app.judgeConnected[message.position] = message.connected;
}
