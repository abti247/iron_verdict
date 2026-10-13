let timerInterval = null;

export function startTimerCountdown(ms, onTick) {
    stopTimer();
    const startedAt = Date.now();

    timerInterval = setInterval(() => {
        const remaining = Math.max(0, ms - (Date.now() - startedAt));
        const seconds = Math.ceil(remaining / 1000);
        onTick(seconds, seconds === 0);

        if (seconds === 0) {
            clearInterval(timerInterval);
            timerInterval = null;
        }
    }, 100);
}

export function stopTimer() {
    if (timerInterval) {
        clearInterval(timerInterval);
        timerInterval = null;
    }
}

// The countdown shown on the judge and display screens, registered as
// Alpine.store('timer'). Started, frozen and reset by connection.js from server messages.
export function createTimerStore() {
    return {
        display: '60',
        expired: false,

        start(ms) {
            startTimerCountdown(ms, (seconds, expired) => {
                this.display = seconds;
                this.expired = expired;
            });
        },

        // Results are in: stop counting and show the time the server froze.
        freeze(frozenMs) {
            stopTimer();
            if (frozenMs != null) this.display = String(Math.ceil(frozenMs / 1000));
        },

        reset() {
            stopTimer();
            this.display = '60';
            this.expired = false;
        },
    };
}
