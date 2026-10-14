// The judge's vote for the current lift and the lift's result, registered as
// Alpine.store('judge'). Server-driven: connection.js writes it from join_success,
// vote_ack/vote_rejected, show_results and reset_for_next_lift; the judge screen
// reads it and calls its vote methods. Delivery (open → sending → confirmed) is in
// voteDelivery.js.

import { CARD_REASONS } from './constants.js';
import { createVoteDeliveryMethods } from './voteDelivery.js';
import { lightColor, cardColor } from './voteLight.js';

const NO_VOTES = () => ({ left: null, center: null, right: null });

// session/settings: the session and settings stores; send: sends a socket message.
export function createJudgeStore({ session, settings, send, storage = sessionStorage }) {
    return {
        selectedVote: null,
        selectedReason: null,
        showingReasonStep: false,
        voteState: 'open',  // 'open' | 'sending' | 'confirmed' — see voteDelivery.js
        voteError: '',      // i18n key of the last vote rejection, '' if none
        liftId: null,
        _pendingVote: null,
        resultsShown: false,
        resultVotes: NO_VOTES(),
        resultReasons: NO_VOTES(),  // translated reason labels
        get voteLocked() { return this.voteState !== 'open'; },

        ...createVoteDeliveryMethods({ session, send, storage }),

        selectVote(color) {
            if (this.voteLocked) return;
            this.voteError = '';
            this.selectedVote = color;
            this.selectedReason = null;
            this.showingReasonStep = (color !== 'white');
        },

        selectReason(reason) {
            this.selectedReason = reason;
        },

        goBackToColorStep() {
            this.showingReasonStep = false;
            this.selectedReason = null;
        },

        // i18n keys of the reasons offered for the selected colour and the session's lift type.
        reasonIds() {
            const liftType = settings.liftType || 'squat';
            return CARD_REASONS[liftType]?.[this.selectedVote] || [];
        },

        canLockIn() {
            if (!this.selectedVote || this.voteLocked) return false;
            if (this.selectedVote === 'white') return true;
            if (settings.requireReasons) return !!this.selectedReason;
            return true;
        },

        resetVoting() {
            this.selectedVote = null;
            this.voteState = 'open';
            this.voteError = '';
            this.clearPendingVote();
            this.resultsShown = false;
            this.selectedReason = null;
            this.showingReasonStep = false;
            this.resultVotes = NO_VOTES();
            this.resultReasons = NO_VOTES();
        },

        // CSS classes of the result light and the card under it at a position.
        resultLightClass(pos) { return lightColor(this.resultVotes[pos]); },
        resultCardClass(pos) { return cardColor(this.resultVotes[pos]); },

        showResults(votes, reasons) {
            this.resultsShown = true;
            this.resultVotes = votes;
            this.resultReasons = reasons;
        },
    };
}
