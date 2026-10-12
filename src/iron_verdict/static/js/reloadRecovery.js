// Reload recovery: after a reload (or the tab reopening the app) a session stored
// in sessionStorage is restored behind a neutral "Connecting…" screen, so the
// landing screen never flashes up. join_success (handlers.js) or the session
// lookup leaves it for the judge, display or role-select screen; a session that
// no longer exists leads to the landing screen with an inline message.

export const reloadRecoveryMethods = {
    // Called from init(). Returns true if a stored session is being restored.
    restoreStoredSession() {
        const stored = sessionStorage.getItem('iv_session');
        if (!stored) return false;
        let code, role;
        try {
            ({ code, role } = JSON.parse(stored));
        } catch (_e) {
            code = null;
        }
        // A session code always has 8 characters; anything else cannot be restored.
        if (typeof code !== 'string' || code.length !== 8) {
            sessionStorage.removeItem('iv_session');
            return false;
        }
        this.sessionCode = code;
        this.joinCode = code;
        // Set before the first render, so no other screen is ever painted.
        this.screen = 'reconnecting';
        // The next screen change replaces the history entry instead of pushing one,
        // so the back-stack keeps the depth it had before the reload (mobile swipe-back).
        this._navigateInPlaceNext = true;
        if (role) {
            this.joinSession(role);
        } else {
            this.joinExistingSession();
        }
        return true;
    },

    cancelReconnect() {
        this.returnToLanding();
    },

    // True if an async step started during reload recovery finished after Cancel.
    isReconnectCancelled(startedWhileReconnecting) {
        return startedWhileReconnecting && this.screen !== 'reconnecting';
    },

    // The stored session no longer exists (ended or expired): back to landing with
    // an inline message instead of a popup.
    failReconnectSessionGone() {
        const code = this.sessionCode;
        this.returnToLanding();
        this.joinError = t('reconnecting.sessionGone').replace('{code}', code);
    },
};
