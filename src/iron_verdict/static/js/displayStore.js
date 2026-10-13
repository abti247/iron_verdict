// What the display screen shows for the current lift, registered as
// Alpine.store('display'). Written by connection.js from show_results and
// reset_for_next_lift; the display screen only reads it.

const NO_VOTES = () => ({ left: null, center: null, right: null });

export function createDisplayStore() {
    return {
        phase: 'idle',  // 'idle' | 'votes'
        votes: NO_VOTES(),
        reasons: NO_VOTES(),  // translated reason labels
        showExplanations: true,
        liftType: 'squat',

        showResults({ votes, reasons, showExplanations, liftType }) {
            this.votes = votes;
            this.reasons = reasons;
            this.showExplanations = showExplanations;
            this.liftType = liftType;
            this.phase = 'votes';
        },

        clear() {
            this.votes = NO_VOTES();
            this.reasons = NO_VOTES();
            this.phase = 'idle';
        },

        isValidLift() {
            const whiteCount = Object.values(this.votes).filter(c => c === 'white').length;
            return whiteCount >= 2;
        },
    };
}
