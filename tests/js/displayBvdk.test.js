import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { displayBvdk } from '../../src/iron_verdict/static/js/screens/displayBvdk.js';
import { createDisplayStore } from '../../src/iron_verdict/static/js/displayStore.js';
import { displayStreamLights } from '../../src/iron_verdict/static/js/screens/displayStreamLights.js';

// The BVDK box of the stream overlay (#215): when it shows, when it is a
// sample, and what it shows while it fades out (the next lift cleared the
// result, or the layout editor closed).

const RESULT = {
    votes: { left: 'red', center: 'white', right: 'white' },
    reasons: { left: 'Depth', center: null, right: null },
    showExplanations: true,
    liftType: 'squat',
};
const OTHER = {
    votes: { left: 'white', center: 'blue', right: 'white' },
    reasons: { left: null, center: 'Soft knees', right: null },
    showExplanations: true,
    liftType: 'squat',
};

function screen({ overlay = true } = {}) {
    const display = createDisplayStore();
    const component = {
        ...displayBvdk(),
        ...displayStreamLights(),  // when a result shows in the stream (#216)
        layoutEditing: false,
        $store: { display, session: { overlay } },
    };
    // What the markup evaluates on every render.
    component.render = () => ({
        shown: component.bvdkShown(),
        sample: component.bvdkIsSample(),
        reasons: component.bvdkView().rows.map((r) => r.reason),
    });
    return component;
}

describe('BVDK box of the stream overlay', () => {
    let c;
    beforeEach(() => { c = screen(); });
    afterEach(() => { vi.unstubAllGlobals(); });

    it('is active only in the overlay with the BVDK view', () => {
        expect(c.bvdkActive()).toBe(true);
        c.overlayLightsView = 'classic';
        expect(c.bvdkActive()).toBe(false);
        expect(screen({ overlay: false }).bvdkActive()).toBe(false);
    });

    it('shows nothing before the result and the current result with it', () => {
        expect(c.render().shown).toBe(false);
        c.$store.display.showResults(RESULT);
        expect(c.render()).toEqual({ shown: true, sample: false, reasons: ['Depth'] });
        c.$store.display.showResults(OTHER);
        expect(c.render().reasons).toEqual(['Soft knees']);
    });

    it('keeps the last result while it fades out after the next lift', () => {
        c.$store.display.showResults(RESULT);
        c.render();
        c.$store.display.clear();
        expect(c.render()).toEqual({ shown: false, sample: false, reasons: ['Depth'] });
    });

    it('shows a sample while editing without a result, the real result with one', () => {
        c.layoutEditing = true;
        const sample = c.render();
        expect(sample.shown).toBe(true);
        expect(sample.sample).toBe(true);
        expect(sample.reasons).toHaveLength(2);
        c.$store.display.showResults(RESULT);
        expect(c.render()).toEqual({ shown: true, sample: false, reasons: ['Depth'] });
    });

    it('keeps the sample (marked as sample) when the editor closes, never an earlier result', () => {
        c.$store.display.showResults(RESULT);
        c.render();
        c.$store.display.clear();
        c.layoutEditing = true;
        const sample = c.render();
        c.layoutEditing = false;
        const leaving = c.render();
        expect(leaving.shown).toBe(false);
        expect(leaving.sample).toBe(true);
        expect(leaving.reasons).toEqual(sample.reasons);
    });

    it('stores the chosen view and reports a choice that cannot be stored', () => {
        const data = {};
        vi.stubGlobal('localStorage', { getItem: (k) => data[k] ?? null, setItem: (k, v) => { data[k] = v; } });
        c.setOverlayLightsView('classic');
        expect(c.overlayLightsView).toBe('classic');
        expect(c.overlayLightsSaveError).toBe(false);
        c.initDisplayBvdk();
        expect(c.overlayLightsView).toBe('classic');
        vi.stubGlobal('localStorage', { getItem: () => null, setItem: () => { throw new Error('blocked'); } });
        c.setOverlayLightsView('bvdk');
        expect(c.overlayLightsSaveError).toBe(true);
    });
});
