import { describe, it, expect } from 'vitest';
import { demoLaunchState } from '../../src/iron_verdict/static/js/screens/demoIntroScreen.js';

// window.open returns a window object, or null when a pop-up blocker stops it;
// some blockers return a window they already closed. The four results of the
// demo launch decide which hint the guide shows (E2E: test_demo_popups.py).
const open = () => ({ closed: false });
const closed = () => ({ closed: true });

describe('demoLaunchState', () => {
    it('all four windows open: demo running, nothing blocked', () => {
        expect(demoLaunchState([open(), open(), open(), open()]))
            .toEqual({ popupsBlocked: 'none', demoRunning: true });
    });

    it('null from the second window on: some blocked, demo not running', () => {
        expect(demoLaunchState([open(), null, null, null]))
            .toEqual({ popupsBlocked: 'some', demoRunning: false });
    });

    it('every window null: all blocked, demo not running', () => {
        expect(demoLaunchState([null, null, null, null]))
            .toEqual({ popupsBlocked: 'all', demoRunning: false });
    });

    it('a window returned already closed counts as blocked, same as null', () => {
        expect(demoLaunchState([open(), open(), closed(), open()]))
            .toEqual({ popupsBlocked: 'some', demoRunning: false });
        expect(demoLaunchState([closed(), closed(), closed(), closed()]))
            .toEqual({ popupsBlocked: 'all', demoRunning: false });
    });
});
