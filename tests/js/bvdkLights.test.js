import { describe, it, expect } from 'vitest';
import {
    bvdkResult, loadLightsView, saveLightsView, LIGHTS_VIEW_STORAGE_KEY,
} from '../../src/iron_verdict/static/js/bvdkLights.js';

const votes = (left, center, right) => ({ left, center, right });
const NO_REASONS = votes(null, null, null);

function memoryStorage(initial = {}) {
    const data = { ...initial };
    return {
        getItem: (k) => (k in data ? data[k] : null),
        setItem: (k, v) => { data[k] = String(v); },
        data,
    };
}

const throwingStorage = {
    getItem() { throw new Error('blocked'); },
    setItem() { throw new Error('blocked'); },
};

describe('bvdkResult', () => {
    it('shows three white lights and no rows for a good lift', () => {
        const r = bvdkResult({ votes: votes('white', 'white', 'white'), reasons: NO_REASONS, showExplanations: true, liftType: 'squat' });
        expect(r.lights).toEqual([
            { pos: 'left', red: false }, { pos: 'center', red: false }, { pos: 'right', red: false },
        ]);
        expect(r.rows).toEqual([]);
    });

    it('gives one row per invalid vote, in judge order, with card colour and reason', () => {
        const r = bvdkResult({
            votes: votes('blue', 'white', 'red'),
            reasons: votes('Supporting contact on legs', null, 'Depth'),
            showExplanations: true,
            liftType: 'squat',
        });
        expect(r.lights.map((l) => l.red)).toEqual([true, false, true]);
        expect(r.rows).toEqual([
            { pos: 'left', index: 0, card: 'blue', reason: 'Supporting contact on legs' },
            { pos: 'right', index: 2, card: 'red', reason: 'Depth' },
        ]);
    });

    it('keeps the row without reason text when reasons are not shown or missing', () => {
        const hidden = bvdkResult({
            votes: votes('yellow', 'white', 'white'),
            reasons: votes('Technical Non-compliance', null, null),
            showExplanations: false,
            liftType: 'bench',
        });
        expect(hidden.rows).toEqual([{ pos: 'left', index: 0, card: 'yellow', reason: '' }]);
        const missing = bvdkResult({ votes: votes('red', 'white', 'white'), reasons: NO_REASONS, showExplanations: true, liftType: 'bench' });
        expect(missing.rows[0].reason).toBe('');
    });

    it.each([['squat', 'SQUAT'], ['bench', 'BENCH'], ['deadlift', 'DEADLIFT']])(
        'names the discipline %s in English (%s)', (liftType, name) => {
            expect(bvdkResult({ votes: votes('white', 'white', 'white'), reasons: NO_REASONS, showExplanations: true, liftType }).discipline)
                .toBe(name);
        });

    it('shows no discipline for an unknown lift type', () => {
        expect(bvdkResult({ votes: votes('white', 'white', 'white'), reasons: NO_REASONS, showExplanations: true, liftType: 'x' }).discipline)
            .toBe('');
    });
});

describe('lights view on this device', () => {
    it('defaults to the BVDK view without a stored choice', () => {
        expect(loadLightsView(memoryStorage())).toBe('bvdk');
    });

    it('stores and loads the classic view', () => {
        const storage = memoryStorage();
        expect(saveLightsView(storage, 'classic')).toBe(true);
        expect(storage.data[LIGHTS_VIEW_STORAGE_KEY]).toBe('classic');
        expect(loadLightsView(storage)).toBe('classic');
        saveLightsView(storage, 'bvdk');
        expect(loadLightsView(storage)).toBe('bvdk');
    });

    it('falls back to the BVDK view for an unknown stored value', () => {
        expect(loadLightsView(memoryStorage({ [LIGHTS_VIEW_STORAGE_KEY]: '<b>x</b>' }))).toBe('bvdk');
    });

    it('falls back to the BVDK view and reports a failed save when storage is blocked or missing', () => {
        expect(loadLightsView(throwingStorage)).toBe('bvdk');
        expect(saveLightsView(throwingStorage, 'classic')).toBe(false);
        expect(loadLightsView(null)).toBe('bvdk');
        expect(saveLightsView(null, 'classic')).toBe(false);
    });
});
