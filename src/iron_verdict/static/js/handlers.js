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

    if (app.isHead) {
        app.requireReasons = message.session_state?.settings?.require_reasons ?? false;
        app.saveSettings();
    }
    const trms = message.session_state?.time_remaining_ms;
    if (trms > 0) {
        app.startTimerCountdown(trms);
    }
}

export function handleJoinError(app, message) {
    if (message.message === 'Role already taken') {
        // Transient race condition — server closes socket, auto-reconnect retries
        return;
    }
    app.ws.close();
    sessionStorage.removeItem('iv_session');
    const sanitizedMessage = document.createTextNode(message.message).textContent;
    alert(`Failed to join session: ${sanitizedMessage}`);
}

export function handleError(app, message) {
    const sanitizedMessage = document.createTextNode(message.message).textContent;
    alert(`Error: ${sanitizedMessage}`);
}

export function handleShowResults(app, message) {
    app.resultsShown = true;
    stopTimer();
    app.judgeResultVotes = message.votes;
    app.judgeResultReasons = message.reasons || { left: null, center: null, right: null };
    if (app.role === 'display') {
        clearTimeout(app._phaseTimer1);
        app.displayVotes = app.judgeResultVotes;
        app.displayReasons = app.judgeResultReasons;
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
        app.displayStatus = 'Waiting for judges...';
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
    alert('Session ended');
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
