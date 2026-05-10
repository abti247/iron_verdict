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

    it('calls onTick with (0, true) at expiry', () => {
        const onTick = vi.fn();
        startTimerCountdown(60000, onTick);
        vi.advanceTimersByTime(60000);
        const calls = onTick.mock.calls;
        expect(calls[calls.length - 1]).toEqual([0, true]);
    });

    it('stops firing after zero — no extra ticks', () => {
        const onTick = vi.fn();
        startTimerCountdown(60000, onTick);
        vi.advanceTimersByTime(60000);
        const countAtZero = onTick.mock.calls.length;
        vi.advanceTimersByTime(1000);
        expect(onTick.mock.calls.length).toBe(countAtZero);
    });

    it('stopTimer cancels a running timer', () => {
        const onTick = vi.fn();
        startTimerCountdown(60000, onTick);
        vi.advanceTimersByTime(100); // one tick
        stopTimer();
        vi.advanceTimersByTime(5000); // would be 50 more ticks
        expect(onTick).toHaveBeenCalledTimes(1);
    });

    it('second startTimerCountdown cancels the first', () => {
        const onTick1 = vi.fn();
        const onTick2 = vi.fn();
        startTimerCountdown(60000, onTick1);
        vi.advanceTimersByTime(100); // onTick1 fires once
        startTimerCountdown(60000, onTick2); // internally calls stopTimer()
        vi.advanceTimersByTime(100); // only onTick2 fires
        expect(onTick1).toHaveBeenCalledTimes(1);
        expect(onTick2).toHaveBeenCalledTimes(1);
    });
});
