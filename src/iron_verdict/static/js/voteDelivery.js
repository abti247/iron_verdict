// Vote delivery for the judge screen: open → sending → confirmed.
//
// A vote counts as locked only once the server answers with vote_ack. Until then it
// is "sending" and kept in sessionStorage, so a dropped connection or a page reload
// cannot lose it: after the next join_success it is reconciled with the server and
// resent if the server does not know it. vote_rejected returns the screen to "open".

const PENDING_KEY = 'iv_pending_vote';

const REJECTION_KEYS = {
    lift_changed: 'judge.voteRejected.liftChanged',
    reason_required: 'judge.voteRejected.reasonRequired',
    invalid: 'judge.voteRejected.invalid',
};

export function savePendingVote(storage, vote) {
    try { storage.setItem(PENDING_KEY, JSON.stringify(vote)); } catch (_e) {}
}

export function loadPendingVote(storage, code, role) {
    try {
        const vote = JSON.parse(storage.getItem(PENDING_KEY));
        if (vote && vote.code === code && vote.role === role) return vote;
    } catch (_e) {}
    return null;
}

export function clearPendingVote(storage) {
    try { storage.removeItem(PENDING_KEY); } catch (_e) {}
}

// Decide what the judge screen shows after (re)joining. The server is authoritative:
// a vote it already has is confirmed; a pending vote it lacks is resent (the server
// rejects it if the lift changed meanwhile); otherwise the screen is open.
export function reconcileVote(serverJudge, pending) {
    if (serverJudge?.locked) {
        return {
            action: 'confirmed',
            color: serverJudge.current_vote,
            reason: serverJudge.current_reason ?? null,
        };
    }
    if (pending) return { action: 'resend', vote: pending };
    return { action: 'open' };
}

export function voteLockMessage(vote) {
    return { type: 'vote_lock', color: vote.color, reason: vote.reason, lift_id: vote.lift_id };
}

export function rejectionKey(code) {
    return REJECTION_KEYS[code] || REJECTION_KEYS.invalid;
}

// Alpine component methods, spread into ironVerdictApp().
// The pending vote is also kept in memory (_pendingVote) so a failing sessionStorage
// write cannot silently lose it on reconnect; storage only adds reload survival.
export const voteDeliveryMethods = {
    _pendingVote: null,

    clearPendingVote() {
        this._pendingVote = null;
        clearPendingVote(sessionStorage);
    },

    lockVote() {
        if (!this.canLockIn()) return;
        const vote = {
            code: this.$store.session.code,
            role: this.$store.session.role,
            lift_id: this.liftId,
            color: this.selectedVote,
            reason: this.selectedVote !== 'white' ? this.selectedReason : null,
        };
        this.voteError = '';
        this.voteState = 'sending';
        this._pendingVote = vote;
        savePendingVote(sessionStorage, vote);
        // If the socket is not open this send is dropped by websocket.js; the vote stays
        // pending and is resent from handleJoinSuccess once the connection is back.
        this.wsSend(voteLockMessage(vote));
    },

    applyVoteAck(message) {
        if (message.lift_id != null && this.liftId != null && message.lift_id !== this.liftId) {
            return;  // ack for a lift this screen has already left (reset_for_next_lift arrived first)
        }
        this.clearPendingVote();
        this.voteState = 'confirmed';
        this.voteError = '';
        this.selectedVote = message.color;
        this.selectedReason = message.reason ?? null;
    },

    applyVoteRejected(message) {
        this.clearPendingVote();
        this.voteState = 'open';
        this.voteError = rejectionKey(message.code);
        if (message.code === 'lift_changed') {
            this.selectedVote = null;
            this.selectedReason = null;
            this.showingReasonStep = false;
        }
    },

    reconcileVoteAfterJoin(serverJudge) {
        const pending = loadPendingVote(sessionStorage, this.$store.session.code, this.$store.session.role) || this._pendingVote;
        const result = reconcileVote(serverJudge, pending);
        if (result.action === 'confirmed') {
            this.clearPendingVote();
            this.voteState = 'confirmed';
            this.selectedVote = result.color;
            this.selectedReason = result.reason;
        } else if (result.action === 'resend') {
            this._pendingVote = result.vote;
            this.voteState = 'sending';
            this.selectedVote = result.vote.color;
            this.selectedReason = result.vote.reason;
            this.showingReasonStep = result.vote.color !== 'white';
            this.wsSend(voteLockMessage(result.vote));
        } else if (this.voteState !== 'open') {
            // Locally locked but unknown to the server: the lift was reset while this
            // screen was offline. Show the open state the server actually has.
            this.resetVoting();
        }
    },
};
