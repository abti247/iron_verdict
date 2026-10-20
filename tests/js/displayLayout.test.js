import { describe, it, expect } from 'vitest';
import {
    LAYOUT_STORAGE_KEY,
    OVERLAY_LAYOUT_STORAGE_KEY,
    LAYOUT_BLOCKS,
    sanitizeLayout,
    loadLayout,
    saveLayout,
    clearLayout,
    layoutFromRects,
    movedBlock,
    scaledBlock,
    cardsWithGap,
    lightsWithGap,
    withBlockHidden,
    blockStyle,
    encodeLayout,
    decodeLayout,
} from '../../src/iron_verdict/static/js/displayLayout.js';

function makeStorage(initial = {}) {
    const data = { ...initial };
    return {
        getItem: (k) => (Object.prototype.hasOwnProperty.call(data, k) ? data[k] : null),
        setItem: (k, v) => { data[k] = String(v); },
        removeItem: (k) => { delete data[k]; },
        data,
    };
}

function validLayout() {
    return {
        v: 1,
        blocks: {
            timer: { x: 30, y: 5, s: 1, hidden: false },
            lights: { x: 20, y: 35, s: 1.5, hidden: false, gap: 0.6 },
            cards: { gap: 0.25, hidden: false },
            verdict: { x: 40, y: 80, s: 1, hidden: true },
            lifter: { x: 2, y: 88, s: 1, hidden: false },
            attempt: { x: 80, y: 88, s: 0.8, hidden: false },
            pause: { x: 50, y: 40, s: 1.2, hidden: false },
        },
    };
}

// A layout saved before the pause block existed (#163).
function layoutWithoutPause() {
    const raw = validLayout();
    delete raw.blocks.pause;
    return raw;
}

describe('sanitizeLayout', () => {
    it('accepts a valid layout unchanged', () => {
        expect(sanitizeLayout(validLayout())).toEqual(validLayout());
    });

    it.each([null, undefined, 'x', 42, [], {}])('rejects %p', (raw) => {
        expect(sanitizeLayout(raw)).toBe(null);
    });

    it('gives a layout without a lights gap (saved before #154) the default gap', () => {
        const raw = validLayout();
        delete raw.blocks.lights.gap;
        expect(sanitizeLayout(raw).blocks.lights.gap).toBe(1);
    });

    it('limits the lights gap and rejects one that is not a number', () => {
        const raw = validLayout();
        raw.blocks.lights.gap = 0.1;
        expect(sanitizeLayout(raw).blocks.lights.gap).toBe(0.4);
        raw.blocks.lights.gap = 9;
        expect(sanitizeLayout(raw).blocks.lights.gap).toBe(2);
        raw.blocks.lights.gap = '1; color: red';
        expect(sanitizeLayout(raw)).toBe(null);
    });

    it('drops a gap on other free blocks', () => {
        const raw = validLayout();
        raw.blocks.timer.gap = 0.5;
        expect(sanitizeLayout(raw).blocks.timer).not.toHaveProperty('gap');
    });

    it('rejects an unknown version', () => {
        expect(sanitizeLayout({ ...validLayout(), v: 2 })).toBe(null);
    });

    it('rejects a layout with a missing block', () => {
        const raw = validLayout();
        delete raw.blocks.timer;
        expect(sanitizeLayout(raw)).toBe(null);
    });

    it('gives a layout without a pause block (saved before #163) a visible default pause block', () => {
        const layout = sanitizeLayout(layoutWithoutPause());
        expect(layout.blocks.pause).toEqual({ x: 50, y: 30, s: 1, hidden: false });
        expect(layout.blocks.timer).toEqual(validLayout().blocks.timer);
    });

    it('hides that default pause block when asked (stream overlay)', () => {
        expect(sanitizeLayout(layoutWithoutPause(), { pauseHidden: true }).blocks.pause.hidden).toBe(true);
        // A stored pause block keeps its own state.
        expect(sanitizeLayout(validLayout(), { pauseHidden: true }).blocks.pause.hidden).toBe(false);
    });

    it('rejects an invalid pause block', () => {
        const raw = validLayout();
        raw.blocks.pause = { x: 'centre', y: 1, s: 1 };
        expect(sanitizeLayout(raw)).toBe(null);
    });

    it('rejects non-numeric positions', () => {
        const raw = validLayout();
        raw.blocks.timer.x = '10%; background: url(evil)';
        expect(sanitizeLayout(raw)).toBe(null);
    });

    it('rejects non-finite numbers', () => {
        const raw = validLayout();
        raw.blocks.lights.s = Infinity;
        expect(sanitizeLayout(raw)).toBe(null);
    });

    it('clamps out-of-range values', () => {
        const raw = validLayout();
        raw.blocks.timer = { x: -20, y: 500, s: 10, hidden: false };
        raw.blocks.lights = { x: 120, y: -5, s: 0, hidden: false };
        raw.blocks.cards = { gap: -1, hidden: false };
        const out = sanitizeLayout(raw);
        expect(out.blocks.timer).toEqual({ x: 0, y: 99, s: 3, hidden: false });
        expect(out.blocks.lights).toMatchObject({ x: 100, y: 0, s: 0.3, hidden: false });
        expect(out.blocks.cards.gap).toBe(0);
    });

    it('treats only true as hidden and drops unknown keys', () => {
        const raw = validLayout();
        raw.blocks.timer.hidden = 'yes';
        raw.blocks.timer.extra = 'x';
        raw.blocks.unknown = { x: 1, y: 1, s: 1 };
        const out = sanitizeLayout(raw);
        expect(out.blocks.timer).toEqual({ x: 30, y: 5, s: 1, hidden: false });
        expect(Object.keys(out.blocks).sort()).toEqual([...LAYOUT_BLOCKS].sort());
    });
});

describe('storage', () => {
    it('has no layout when nothing is stored', () => {
        expect(loadLayout(makeStorage())).toBe(null);
    });

    it('round-trips a saved layout', () => {
        const storage = makeStorage();
        expect(saveLayout(storage, validLayout())).toBe(true);
        expect(loadLayout(storage)).toEqual(validLayout());
    });

    it('ignores broken JSON', () => {
        expect(loadLayout(makeStorage({ [LAYOUT_STORAGE_KEY]: '{not json' }))).toBe(null);
    });

    it('ignores an invalid stored layout', () => {
        expect(loadLayout(makeStorage({ [LAYOUT_STORAGE_KEY]: '{"v":1}' }))).toBe(null);
    });

    it('clears the stored layout', () => {
        const storage = makeStorage();
        saveLayout(storage, validLayout());
        clearLayout(storage);
        expect(loadLayout(storage)).toBe(null);
    });

    it('survives a storage that throws', () => {
        const broken = {
            getItem: () => { throw new Error('blocked'); },
            setItem: () => { throw new Error('blocked'); },
            removeItem: () => { throw new Error('blocked'); },
        };
        expect(loadLayout(broken)).toBe(null);
        expect(saveLayout(broken, validLayout())).toBe(false);
        expect(clearLayout(broken)).toBe(false);
        expect(saveLayout(null, validLayout())).toBe(false);
        expect(loadLayout(null)).toBe(null);
    });
});

describe('layoutFromRects', () => {
    const rect = (left, top, width) => ({ left, top, right: left + width, width });

    it('turns measured blocks into their anchor point in percent of the display, unscaled and visible', () => {
        const root = { left: 0, top: 0, width: 1000, height: 500 };
        const layout = layoutFromRects(root, {
            timer: rect(400, 10, 200),
            lights: rect(200, 150, 600),
            verdict: rect(450, 400, 100),
            lifter: rect(20, 450, 300),
            attempt: rect(800, 450, 180),
            pause: rect(300, 100, 400),
        });
        expect(layout.v).toBe(1);
        expect(layout.blocks.pause).toEqual({ x: 50, y: 20, s: 1, hidden: false });
        expect(layout.blocks.timer).toEqual({ x: 50, y: 2, s: 1, hidden: false });
        expect(layout.blocks.lights).toEqual({ x: 50, y: 30, s: 1, hidden: false, gap: 1 });
        expect(layout.blocks.lifter).toEqual({ x: 2, y: 90, s: 1, hidden: false });
        expect(layout.blocks.attempt).toEqual({ x: 98, y: 90, s: 1, hidden: false });
        expect(layout.blocks.cards).toEqual({ gap: 0, hidden: false });
    });

    it('measures relative to the display, not the page', () => {
        const root = { left: 100, top: 50, width: 1000, height: 500 };
        const r = rect(150, 100, 0);
        const layout = layoutFromRects(root, { timer: r, lights: r, verdict: r, lifter: r, attempt: r, pause: r });
        expect(layout.blocks.lifter.x).toBe(5);
        expect(layout.blocks.lifter.y).toBe(10);
    });
});

describe('layoutFromRects for the pause block', () => {
    it('starts the measured pause block hidden when asked (stream overlay)', () => {
        const root = { left: 0, top: 0, width: 1000, height: 500 };
        const r = { left: 0, top: 0, right: 10, width: 10 };
        const rects = { timer: r, lights: r, verdict: r, lifter: r, attempt: r, pause: r };
        expect(layoutFromRects(root, rects, { pauseHidden: true }).blocks.pause.hidden).toBe(true);
        expect(layoutFromRects(root, rects).blocks.pause.hidden).toBe(false);
    });
});

describe('block edits', () => {
    const block = { x: 10.4, y: 20.6, s: 1, hidden: false };

    it('moves in 1 % steps', () => {
        expect(movedBlock(block, 5.3, -2.2)).toEqual({ x: 16, y: 18, s: 1, hidden: false });
    });

    it('keeps the anchor point on screen', () => {
        expect(movedBlock(block, -50, 200)).toMatchObject({ x: 0, y: 99 });
        expect(movedBlock(block, 150, -50)).toMatchObject({ x: 100, y: 0 });
    });

    it('scales in 5 % steps', () => {
        expect(scaledBlock(block, 1.33).s).toBe(1.35);
        expect(scaledBlock({ ...block, s: 1.5 }, 1.1).s).toBe(1.65);
    });

    it('limits the scale', () => {
        expect(scaledBlock(block, 0.01).s).toBe(0.3);
        expect(scaledBlock(block, 100).s).toBe(3);
    });

    it('sets the card gap in 5 % steps of the light, never negative', () => {
        const cards = { gap: 0, hidden: false };
        expect(cardsWithGap(cards, 0.42)).toEqual({ gap: 0.4, hidden: false });
        expect(cardsWithGap(cards, -1).gap).toBe(0);
        expect(cardsWithGap(cards, 50).gap).toBe(2);
    });

    it('sets the lights gap in 5 % steps of the default gap, from 0.4 to 2', () => {
        const lights = { x: 50, y: 30, s: 1, hidden: false, gap: 1 };
        expect(lightsWithGap(lights, 0.72)).toEqual({ ...lights, gap: 0.7 });
        expect(lightsWithGap(lights, 0).gap).toBe(0.4);
        expect(lightsWithGap(lights, 50).gap).toBe(2);
    });

    it('hides and shows a block without touching the others', () => {
        const layout = validLayout();
        const out = withBlockHidden(layout, 'timer', true);
        expect(out.blocks.timer.hidden).toBe(true);
        expect(out.blocks.lights).toEqual(layout.blocks.lights);
        expect(layout.blocks.timer.hidden).toBe(false);
    });
});

describe('blockStyle', () => {
    const block = { x: 12, y: 34.5, s: 1.25, hidden: false };

    it('positions a left-anchored block by its left edge and scales it', () => {
        expect(blockStyle(block, 'left'))
            .toEqual({ left: '12%', top: '34.5%', transform: 'translateX(0)', '--display-zoom': '1.25' });
    });

    it('positions centred and right-anchored blocks by their centre and right edge', () => {
        expect(blockStyle(block, 'center').transform).toBe('translateX(-50%)');
        expect(blockStyle(block, 'right').transform).toBe('translateX(-100%)');
    });

    it('unsets every property without a block', () => {
        expect(blockStyle(null, 'center')).toEqual({ left: '', top: '', transform: '', '--display-zoom': '' });
    });
});

describe('export code', () => {
    it('round-trips a layout', () => {
        const code = encodeLayout(validLayout());
        expect(code).toMatch(/^IV1\.[A-Za-z0-9_-]+$/);
        expect(decodeLayout(code)).toEqual(validLayout());
    });

    it('tolerates surrounding whitespace', () => {
        expect(decodeLayout(`  ${encodeLayout(validLayout())}\n`)).toEqual(validLayout());
    });

    it('gives an old code without a pause block the default pause block (hidden when asked)', () => {
        const code = encodeLayout(layoutWithoutPause());
        expect(decodeLayout(code).blocks.pause.hidden).toBe(false);
        expect(decodeLayout(code, { pauseHidden: true }).blocks.pause.hidden).toBe(true);
    });

    it.each(['', 'hello', 'IV1.', 'IV1.!!!', 'IV2.e30', 'IV1.e30'])('rejects %p', (code) => {
        expect(decodeLayout(code)).toBe(null);
    });
});

describe('layout storage key', () => {
    it('keeps the overlay layout apart from the hall display layout', () => {
        const storage = makeStorage();
        const overlay = { ...validLayout(), blocks: { ...validLayout().blocks, timer: { x: 1, y: 1, s: 1, hidden: true } } };
        expect(saveLayout(storage, validLayout())).toBe(true);
        expect(saveLayout(storage, overlay, OVERLAY_LAYOUT_STORAGE_KEY)).toBe(true);
        expect(loadLayout(storage)).toEqual(validLayout());
        expect(loadLayout(storage, OVERLAY_LAYOUT_STORAGE_KEY)).toEqual(overlay);
        expect(clearLayout(storage, OVERLAY_LAYOUT_STORAGE_KEY)).toBe(true);
        expect(loadLayout(storage, OVERLAY_LAYOUT_STORAGE_KEY)).toBe(null);
        expect(loadLayout(storage)).toEqual(validLayout());
        expect(OVERLAY_LAYOUT_STORAGE_KEY).not.toBe(LAYOUT_STORAGE_KEY);
    });

    it('hides the default pause block of an old layout only in the stream overlay', () => {
        const old = JSON.stringify(layoutWithoutPause());
        const storage = makeStorage({ [LAYOUT_STORAGE_KEY]: old, [OVERLAY_LAYOUT_STORAGE_KEY]: old });
        expect(loadLayout(storage).blocks.pause.hidden).toBe(false);
        expect(loadLayout(storage, OVERLAY_LAYOUT_STORAGE_KEY).blocks.pause.hidden).toBe(true);
    });
});
