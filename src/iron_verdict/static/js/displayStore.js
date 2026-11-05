// What the display screen shows for the current lift, registered as
// Alpine.store('display'). Written by connection.js from show_results and
// reset_for_next_lift; the display screen only reads it.
//
// Stream overlay (#216): only a result that arrives live shows in the stream
// (streamShown). The result the server replays after a join in the results
// phase (reload, reconnect) is restored for the hall display but never shown
// again in the stream; join_success announces it (expectRestoredResult).

import { lightColor, cardColor } from './voteLight.js';

const NO_VOTES = () => ({ left: null, center: null, right: null });

export function createDisplayStore() {
    return {
        phase: 'idle',  // 'idle' | 'votes'
        votes: NO_VOTES(),
        reasons: NO_VOTES(),  // translated reason labels
        showExplanations: true,
        liftType: 'squat',
        streamShown: false,             // the stream overlay shows the current result
        liveResults: 0,                 // bumped by every live result (restarts the overlay's duration)
        restoredResultExpected: false,  // the next show_results is the replay after a join

        // live: false for the replay after a join (a reconnect while the result
        // still shows keeps showing it, a reload does not show it again).
        showResults({ votes, reasons, showExplanations, liftType, live = true }) {
            this.votes = votes;
            this.reasons = reasons;
            this.showExplanations = showExplanations;
            this.liftType = liftType;
            this.phase = 'votes';
            this.restoredResultExpected = false;
            if (live) {
                this.streamShown = true;
                this.liveResults += 1;
            }
        },

        expectRestoredResult(expected) {
            this.restoredResultExpected = expected;
        },

        hideFromStream() {
            this.streamShown = false;
        },

        clear() {
            this.votes = NO_VOTES();
            this.reasons = NO_VOTES();
            this.phase = 'idle';
            this.streamShown = false;
            this.restoredResultExpected = false;
        },

        // CSS classes of the light and the card under it at a position.
        lightClass(pos) { return lightColor(this.votes[pos]); },
        cardClass(pos) { return cardColor(this.votes[pos]); },

        isValidLift() {
            const whiteCount = Object.values(this.votes).filter(c => c === 'white').length;
            return whiteCount >= 2;
        },
    };
}
