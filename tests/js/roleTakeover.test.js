import { describe, it, expect } from 'vitest';
import {
    ROLE_TAKEN_GIVE_UP_MS,
    createRoleTakenTracker,
    roleTakenNotice,
} from '../../src/iron_verdict/static/js/roleTakeover.js';

function clock(start = 1000) {
    const c = { t: start, now: () => c.t };
    return c;
}

describe('role taken tracker', () => {
    it('keeps retrying until the give-up limit since the first rejection', () => {
        const c = clock();
        const tracker = createRoleTakenTracker(c.now);
        expect(tracker.rejectedShouldGiveUp()).toBe(false);
        c.t += ROLE_TAKEN_GIVE_UP_MS - 1;
        expect(tracker.rejectedShouldGiveUp()).toBe(false);
        c.t += 1;
        expect(tracker.rejectedShouldGiveUp()).toBe(true);
    });

    it('starts a new streak after a reset (successful join)', () => {
        const c = clock();
        const tracker = createRoleTakenTracker(c.now);
        tracker.rejectedShouldGiveUp();
        c.t += ROLE_TAKEN_GIVE_UP_MS - 1000;
        tracker.reset();
        c.t += 2000;
        expect(tracker.rejectedShouldGiveUp()).toBe(false);
        c.t += ROLE_TAKEN_GIVE_UP_MS;
        expect(tracker.rejectedShouldGiveUp()).toBe(true);
    });
});

describe('role taken notice', () => {
    const t = (key) => ({
        'roles.left': 'Left Judge',
        'roles.chiefReferee': 'Chief\nReferee',
        'roles.right': 'Right Judge',
        'roleTakenOver.notice': '{role} is now signed in on another device',
    })[key];

    it('names the position that was taken', () => {
        expect(roleTakenNotice(t, 'left_judge')).toBe('Left Judge is now signed in on another device');
        expect(roleTakenNotice(t, 'right_judge')).toBe('Right Judge is now signed in on another device');
    });

    it('puts a multi-line role label on one line', () => {
        expect(roleTakenNotice(t, 'center_judge')).toBe('Chief Referee is now signed in on another device');
    });
});
