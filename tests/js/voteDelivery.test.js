import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
    savePendingVote,
    loadPendingVote,
    clearPendingVote,
    reconcileVote,
    voteLockMessage,
    rejectionKey,
} from '../../src/iron_verdict/static/js/voteDelivery.js';
import { createJudgeStore } from '../../src/iron_verdict/static/js/judgeStore.js';
import { createTimerStore } from '../../src/iron_verdict/static/js/timer.js';
import { handleResetForNextLift } from '../../src/iron_verdict/static/js/handlers.js';

const vote = { code: 'ABCD1234', role: 'left_judge', lift_id: 3, color: 'red', reason: 'reasons.squat.red.depth' };

describe('pending vote storage', () => {
    beforeEach(() => sessionStorage.clear());

    it('round-trips a pending vote for the same session and role', () => {
        savePendingVote(sessionStorage, vote);
        expect(loadPendingVote(sessionStorage, 'ABCD1234', 'left_judge')).toEqual(vote);
    });

    it('ignores a pending vote from another session or role', () => {
        savePendingVote(sessionStorage, vote);
        expect(loadPendingVote(sessionStorage, 'ZZZZ9999', 'left_judge')).toBeNull();
        expect(loadPendingVote(sessionStorage, 'ABCD1234', 'right_judge')).toBeNull();
    });

    it('returns null for missing or corrupt data', () => {
        expect(loadPendingVote(sessionStorage, 'ABCD1234', 'left_judge')).toBeNull();
        sessionStorage.setItem('iv_pending_vote', '{not json');
        expect(loadPendingVote(sessionStorage, 'ABCD1234', 'left_judge')).toBeNull();
    });

    it('clears the pending vote', () => {
        savePendingVote(sessionStorage, vote);
        clearPendingVote(sessionStorage);
        expect(loadPendingVote(sessionStorage, 'ABCD1234', 'left_judge')).toBeNull();
    });
});

describe('reconcileVote', () => {
    it('confirms the server vote when the server has one, even with a pending vote', () => {
        const server = { locked: true, current_vote: 'white', current_reason: null };
        expect(reconcileVote(server, vote)).toEqual({ action: 'confirmed', color: 'white', reason: null });
    });

    it('resends a pending vote the server does not know', () => {
        expect(reconcileVote({ locked: false }, vote)).toEqual({ action: 'resend', vote });
    });

    it('is open when neither side has a vote', () => {
        expect(reconcileVote({ locked: false }, null)).toEqual({ action: 'open' });
        expect(reconcileVote(undefined, null)).toEqual({ action: 'open' });
    });
});

describe('message helpers', () => {
    it('builds vote_lock with the lift id', () => {
        expect(voteLockMessage(vote)).toEqual({
            type: 'vote_lock', color: 'red', reason: 'reasons.squat.red.depth', lift_id: 3,
        });
    });

    it('maps rejection codes to i18n keys, unknown codes to the generic one', () => {
        expect(rejectionKey('lift_changed')).toBe('judge.voteRejected.liftChanged');
        expect(rejectionKey('reason_required')).toBe('judge.voteRejected.reasonRequired');
        expect(rejectionKey('something_new')).toBe('judge.voteRejected.invalid');
    });
});

// The judge store with its vote delivery methods, as the judge screen uses it.
function makeApp(overrides = {}) {
    const send = vi.fn();
    const app = createJudgeStore({
        session: { code: 'ABCD1234', role: 'left_judge' },
        settings: { requireReasons: false },
        send,
        storage: sessionStorage,
    });
    Object.assign(app, { liftId: 3, ...overrides });
    app.send = send;
    vi.spyOn(app, 'resetVoting');
    return app;
}

describe('judge store vote delivery', () => {
    beforeEach(() => sessionStorage.clear());

    it('lockVote goes to sending, stores the vote and sends it', () => {
        const app = makeApp({ selectedVote: 'white', voteError: 'judge.voteRejected.invalid' });
        app.lockVote();
        expect(app.voteState).toBe('sending');
        expect(app.voteError).toBe('');
        expect(app.send).toHaveBeenCalledWith({ type: 'vote_lock', color: 'white', reason: null, lift_id: 3 });
        expect(loadPendingVote(sessionStorage, 'ABCD1234', 'left_judge')).toMatchObject({ color: 'white', lift_id: 3 });
    });

    it('lockVote does nothing when lock-in is not allowed', () => {
        const app = makeApp();
        app.lockVote();
        expect(app.voteState).toBe('open');
        expect(app.send).not.toHaveBeenCalled();
    });

    it('vote_ack confirms and clears the pending vote', () => {
        const app = makeApp({ selectedVote: 'red', voteState: 'sending' });
        savePendingVote(sessionStorage, vote);
        app.applyVoteAck({ color: 'red', reason: 'reasons.squat.red.depth', lift_id: 3 });
        expect(app.voteState).toBe('confirmed');
        expect(app.selectedReason).toBe('reasons.squat.red.depth');
        expect(loadPendingVote(sessionStorage, 'ABCD1234', 'left_judge')).toBeNull();
    });

    it('vote_ack shows the server vote when it differs from the local one', () => {
        const app = makeApp({ selectedVote: 'red', voteState: 'sending' });
        app.applyVoteAck({ color: 'white', reason: null, lift_id: 3 });
        expect(app.selectedVote).toBe('white');
    });

    it('vote_ack for an earlier lift is ignored', () => {
        const app = makeApp({ liftId: 4 });
        app.applyVoteAck({ color: 'white', reason: null, lift_id: 3 });
        expect(app.voteState).toBe('open');
    });

    it('vote_rejected reopens voting with a message', () => {
        const app = makeApp({ selectedVote: 'red', voteState: 'sending', showingReasonStep: true });
        savePendingVote(sessionStorage, vote);
        app.applyVoteRejected({ code: 'reason_required' });
        expect(app.voteState).toBe('open');
        expect(app.voteError).toBe('judge.voteRejected.reasonRequired');
        expect(app.selectedVote).toBe('red');
        expect(loadPendingVote(sessionStorage, 'ABCD1234', 'left_judge')).toBeNull();
    });

    it('vote_rejected for a changed lift clears the selection', () => {
        const app = makeApp({ selectedVote: 'red', voteState: 'sending', showingReasonStep: true });
        app.applyVoteRejected({ code: 'lift_changed' });
        expect(app.selectedVote).toBeNull();
        expect(app.showingReasonStep).toBe(false);
    });

    it('after join, resends a pending vote the server lacks', () => {
        const app = makeApp();
        savePendingVote(sessionStorage, vote);
        app.reconcileVoteAfterJoin({ locked: false });
        expect(app.voteState).toBe('sending');
        expect(app.selectedVote).toBe('red');
        expect(app.send).toHaveBeenCalledWith(voteLockMessage(vote));
    });

    it('after join, confirms the vote the server has', () => {
        const app = makeApp({ voteState: 'sending' });
        savePendingVote(sessionStorage, vote);
        app.reconcileVoteAfterJoin({ locked: true, current_vote: 'red', current_reason: null });
        expect(app.voteState).toBe('confirmed');
        expect(app.send).not.toHaveBeenCalled();
        expect(loadPendingVote(sessionStorage, 'ABCD1234', 'left_judge')).toBeNull();
    });

    it('after join, a locally locked vote unknown to the server resets voting', () => {
        const app = makeApp({ voteState: 'confirmed', selectedVote: 'white' });
        app.reconcileVoteAfterJoin({ locked: false });
        expect(app.resetVoting).toHaveBeenCalled();
    });

    it('after join, an open screen keeps its unlocked selection', () => {
        const app = makeApp({ selectedVote: 'red' });
        app.reconcileVoteAfterJoin({ locked: false });
        expect(app.resetVoting).not.toHaveBeenCalled();
        expect(app.selectedVote).toBe('red');
    });
});

describe('vote delivery edge cases', () => {
    beforeEach(() => sessionStorage.clear());

    it('resends from memory when sessionStorage could not store the pending vote', () => {
        const app = makeApp({ selectedVote: 'white' });
        const setItem = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
            throw new Error('QuotaExceededError');
        });
        try {
            app.lockVote();
        } finally {
            setItem.mockRestore();
        }
        expect(loadPendingVote(sessionStorage, 'ABCD1234', 'left_judge')).toBeNull();
        app.send.mockClear();

        app.reconcileVoteAfterJoin({ locked: false });

        expect(app.voteState).toBe('sending');
        expect(app.resetVoting).not.toHaveBeenCalled();
        expect(app.send).toHaveBeenCalledWith({ type: 'vote_lock', color: 'white', reason: null, lift_id: 3 });
    });

    function connectionFor(judge) {
        return { judge, timer: createTimerStore(), session: { role: 'left_judge' } };
    }

    it('reset_for_next_lift while a vote is sending reopens voting with the lift-changed message', () => {
        const app = makeApp({ selectedVote: 'white', voteState: 'sending' });
        savePendingVote(sessionStorage, vote);
        app._pendingVote = vote;

        handleResetForNextLift(connectionFor(app), { type: 'reset_for_next_lift', lift_id: 4 });

        expect(app.voteState).toBe('open');
        expect(app.liftId).toBe(4);
        expect(app.voteError).toBe('judge.voteRejected.liftChanged');
        expect(app._pendingVote).toBeNull();
        expect(loadPendingVote(sessionStorage, 'ABCD1234', 'left_judge')).toBeNull();
    });

    it('reset_for_next_lift after a confirmed vote shows no message', () => {
        const app = makeApp({ voteState: 'confirmed' });

        handleResetForNextLift(connectionFor(app), { type: 'reset_for_next_lift', lift_id: 4 });

        expect(app.voteError).toBe('');
    });
});
