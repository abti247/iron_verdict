// Display layout: where each block of the display screen sits and how large it
// is, stored per device (localStorage). Pure functions only; the editor in
// screens/displayLayoutEditor.js drives them. No layout (null) means the
// default flow layout of layout.css, so a display that never edits looks as
// before.
//
// Free blocks have x/y (top-left corner, percent of the display) and s (scale,
// applied as the block's --display-zoom). The cards block (card colours and
// reasons under the lights) follows the lights: it only has a gap, in
// multiples of the light size. Every block can be hidden.

export const LAYOUT_STORAGE_KEY = 'iron-verdict:display-layout';
export const FREE_BLOCKS = ['timer', 'lights', 'verdict', 'lifter', 'attempt'];
export const LAYOUT_BLOCKS = [...FREE_BLOCKS, 'cards'];

const VERSION = 1;
const CODE_PREFIX = 'IV1.';
const POS_MAX = 99;           // the top-left corner stays on screen
const SCALE_MIN = 0.3;
const SCALE_MAX = 3;
const SCALE_STEP = 0.05;
const GAP_MAX = 2;
const GAP_STEP = 0.05;

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
// Two decimals hide float noise (1.5 * 1.1 → 1.6500000000000001).
const tidy = (v) => Math.round(v * 100) / 100;
const snap = (v, step) => tidy(Math.round(v / step) * step);

const isNum = (v) => typeof v === 'number' && Number.isFinite(v);

function sanitizeFree(raw) {
    if (!raw || typeof raw !== 'object') return null;
    const { x, y, s } = raw;
    if (!isNum(x) || !isNum(y) || !isNum(s)) return null;
    return {
        x: clamp(x, 0, POS_MAX),
        y: clamp(y, 0, POS_MAX),
        s: clamp(s, SCALE_MIN, SCALE_MAX),
        hidden: raw.hidden === true,
    };
}

function sanitizeCards(raw) {
    if (!raw || typeof raw !== 'object' || !isNum(raw.gap)) return null;
    return { gap: clamp(raw.gap, 0, GAP_MAX), hidden: raw.hidden === true };
}

// Returns a clean copy of a layout, or null if it is not a complete, known
// layout. Only numbers and booleans survive, so a stored or imported layout
// can never inject CSS into blockStyle().
export function sanitizeLayout(raw) {
    if (!raw || typeof raw !== 'object' || raw.v !== VERSION) return null;
    const src = raw.blocks;
    if (!src || typeof src !== 'object') return null;
    const blocks = {};
    for (const id of FREE_BLOCKS) {
        blocks[id] = sanitizeFree(src[id]);
        if (!blocks[id]) return null;
    }
    blocks.cards = sanitizeCards(src.cards);
    if (!blocks.cards) return null;
    return { v: VERSION, blocks };
}

export function loadLayout(storage) {
    try {
        const raw = storage.getItem(LAYOUT_STORAGE_KEY);
        return raw == null ? null : sanitizeLayout(JSON.parse(raw));
    } catch (_) {
        return null;
    }
}

export function saveLayout(storage, layout) {
    try { storage.setItem(LAYOUT_STORAGE_KEY, JSON.stringify(layout)); } catch (_) {}
}

export function clearLayout(storage) {
    try { storage.removeItem(LAYOUT_STORAGE_KEY); } catch (_) {}
}

// A layout that puts every free block where it is now (rects from
// getBoundingClientRect), so leaving the flow layout does not move anything.
export function layoutFromRects(root, rects) {
    const blocks = {};
    for (const id of FREE_BLOCKS) {
        const r = rects[id];
        blocks[id] = {
            x: tidy(((r.left - root.left) / root.width) * 100),
            y: tidy(((r.top - root.top) / root.height) * 100),
            s: 1,
            hidden: false,
        };
    }
    blocks.cards = { gap: 0, hidden: false };
    return { v: VERSION, blocks };
}

// dx/dy in percent of the display; snaps to 1 %.
export function movedBlock(block, dx, dy) {
    return {
        ...block,
        x: clamp(Math.round(block.x + dx), 0, POS_MAX),
        y: clamp(Math.round(block.y + dy), 0, POS_MAX),
    };
}

export function scaledBlock(block, ratio) {
    return { ...block, s: clamp(snap(block.s * ratio, SCALE_STEP), SCALE_MIN, SCALE_MAX) };
}

export function cardsWithGap(cards, gap) {
    return { ...cards, gap: clamp(snap(gap, GAP_STEP), 0, GAP_MAX) };
}

export function withBlockHidden(layout, id, hidden) {
    return { ...layout, blocks: { ...layout.blocks, [id]: { ...layout.blocks[id], hidden } } };
}

export function blockStyle(block) {
    return `left: ${block.x}%; top: ${block.y}%; --display-zoom: ${block.s}`;
}

// Export code: "IV1." + base64url(JSON). Layouts hold only ASCII, so btoa is safe.
export function encodeLayout(layout) {
    const b64 = btoa(JSON.stringify(layout));
    return CODE_PREFIX + b64.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

export function decodeLayout(code) {
    const text = String(code || '').trim();
    if (!text.startsWith(CODE_PREFIX)) return null;
    const body = text.slice(CODE_PREFIX.length);
    if (!/^[A-Za-z0-9_-]+$/.test(body)) return null;
    try {
        const b64 = body.replace(/-/g, '+').replace(/_/g, '/');
        return sanitizeLayout(JSON.parse(atob(b64)));
    } catch (_) {
        return null;
    }
}
