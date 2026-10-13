// Reload recovery: after a reload (or the tab reopening the app) a session stored
// in sessionStorage is restored behind a neutral "Connecting…" screen, so the
// landing screen never flashes up. join_success (handlers.js) or the session
// lookup leaves it for the judge, display or role-select screen; a session that
// no longer exists leads to the landing screen with an inline message.

// `c` is the connection (connection.js): its stores, storage and flows.

// Called on start. Returns true if a stored session is being restored.
export function restoreStoredSession(c) {
    const stored = c.storage.getItem('iv_session');
    if (!stored) return false;
    let code, role;
    try {
        ({ code, role } = JSON.parse(stored));
    } catch (_e) {
        code = null;
    }
    // A session code always has 8 characters; anything else cannot be restored.
    if (typeof code !== 'string' || code.length !== 8) {
        c.storage.removeItem('iv_session');
        return false;
    }
    c.session.code = code;
    c.session.joinCode = code;
    // Set before the first render, so no other screen is ever painted.
    c.nav.screen = 'reconnecting';
    // The next screen change replaces the history entry instead of pushing one,
    // so the back-stack keeps the depth it had before the reload (mobile swipe-back).
    c.nav.navigateInPlaceNext = true;
    if (role) {
        c.joinSession(role);
    } else {
        c.lookupSession();
    }
    return true;
}

// True if an async step started during reload recovery finished after Cancel.
export function isReconnectCancelled(c, startedWhileReconnecting) {
    return startedWhileReconnecting && c.nav.screen !== 'reconnecting';
}

// The stored session no longer exists (ended or expired): back to landing with
// an inline message instead of a popup.
export function failReconnectSessionGone(c) {
    const code = c.session.code;
    c.returnToLanding();
    c.session.joinError = c.t('reconnecting.sessionGone').replace('{code}', code);
}
