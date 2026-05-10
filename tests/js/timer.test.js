import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { startTimerCountdown, stopTimer } from '../../src/iron_verdict/static/js/timer.js';

describe('timer', () => {
    beforeEach(() => {
        vi.useFakeTimers();
    });

    afterEach(() => {
        stopTimer();
        vi.useRealTimers();
    });

    it('calls onTick with correct seconds on first tick', () => {
        const onTick = vi.fn();
        startTimerCountdown(60000, onTick);
        vi.advanceTimersByTime(100);
        // After 100ms: remaining = 59900ms → ceil(59.9) = 60
        expect(onTick).toHaveBeenCalledWith(60, false);
    });
});
