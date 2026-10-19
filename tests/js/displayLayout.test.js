import { describe, it, expect } from 'vitest';
import {
    LAYOUT_STORAGE_KEY,
    LAYOUT_BLOCKS,
    sanitizeLayout,
    loadLayout,
    saveLayout,
    clearLayout,
    layoutFromRects,
    movedBlock,
    scaledBlock,
    cardsWithGap,
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
            lights: { x: 20, y: 35, s: 1.5, hidden: false },
            cards: { gap: 0.25, hidden: false },
            verdict: { x: 40, y: 80, s: 1, hidden: true },
            lifter: { x: 2, y: 88, s: 1, hidden: false },
            attempt: { x: 80, y: 88, s: 0.8, hidden: false },
        },
    };
}

describe('sanitizeLayout', () => {
    it('accepts a valid layout unchanged', () => {
        expect(sanitizeLayout(validLayout())).toEqual(validLayout());
    });

    it.each([null, undefined, 'x', 42, [], {}])('rejects %p', (raw) => {
        expect(sanitizeLayout(raw)).toBe(null);
    });

    it('rejects an unknown version', () => {
        expect(sanitizeLayout({ ...validLayout(), v: 2 })).toBe(null);
    });

    it('rejects a layout with a missing block', () => {
        const raw = validLayout();
        delete raw.blocks.timer;
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
        raw.blocks.cards = { gap: -1, hidden: false };
        const out = sanitizeLayout(raw);
        expect(out.blocks.timer).toEqual({ x: 0, y: 99, s: 3, hidden: false });
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
        saveLayout(storage, validLayout());
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
        expect(() => saveLayout(broken, validLayout())).not.toThrow();
        expect(() => clearLayout(broken)).not.toThrow();
    });
});

describe('layoutFromRects', () => {
    it('turns measured block positions into percent of the display, unscaled and visible', () => {
        const root = { left: 0, top: 0, width: 1000, height: 500 };
        const rect = (left, top) => ({ left, top });
        const layout = layoutFromRects(root, {
            timer: rect(400, 10),
            lights: rect(200, 150),
            verdict: rect(450, 400),
            lifter: rect(20, 450),
            attempt: rect(900, 450),
        });
        expect(layout.v).toBe(1);
        expect(layout.blocks.timer).toEqual({ x: 40, y: 2, s: 1, hidden: false });
        expect(layout.blocks.lights).toEqual({ x: 20, y: 30, s: 1, hidden: false });
        expect(layout.blocks.attempt).toEqual({ x: 90, y: 90, s: 1, hidden: false });
        expect(layout.blocks.cards).toEqual({ gap: 0, hidden: false });
    });

    it('measures relative to the display, not the page', () => {
        const root = { left: 100, top: 50, width: 1000, height: 500 };
        const r = { left: 150, top: 100 };
        const layout = layoutFromRects(root, { timer: r, lights: r, verdict: r, lifter: r, attempt: r });
        expect(layout.blocks.timer.x).toBe(5);
        expect(layout.blocks.timer.y).toBe(10);
    });
});

describe('block edits', () => {
    const block = { x: 10.4, y: 20.6, s: 1, hidden: false };

    it('moves in 1 % steps', () => {
        expect(movedBlock(block, 5.3, -2.2)).toEqual({ x: 16, y: 18, s: 1, hidden: false });
    });

    it('keeps the top-left corner on screen', () => {
        expect(movedBlock(block, -50, 200)).toMatchObject({ x: 0, y: 99 });
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

    it('hides and shows a block without touching the others', () => {
        const layout = validLayout();
        const out = withBlockHidden(layout, 'timer', true);
        expect(out.blocks.timer.hidden).toBe(true);
        expect(out.blocks.lights).toEqual(layout.blocks.lights);
        expect(layout.blocks.timer.hidden).toBe(false);
    });
});

describe('blockStyle', () => {
    it('positions and scales a block', () => {
        expect(blockStyle({ x: 12, y: 34.5, s: 1.25, hidden: false }))
            .toEqual({ left: '12%', top: '34.5%', '--display-zoom': '1.25' });
    });

    it('unsets every property without a block', () => {
        expect(blockStyle(null)).toEqual({ left: '', top: '', '--display-zoom': '' });
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

    it.each(['', 'hello', 'IV1.', 'IV1.!!!', 'IV2.e30', 'IV1.e30'])('rejects %p', (code) => {
        expect(decodeLayout(code)).toBe(null);
    });
});
