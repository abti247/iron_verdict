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
