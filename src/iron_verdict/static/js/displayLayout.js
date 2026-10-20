// Display layout: where each block of the display screen sits and how large it
// is, stored per device (localStorage; the stream overlay under its own key). Pure functions only; the editor in
// screens/displayLayoutEditor.js drives them. No layout (null) means the
// default flow layout of layout.css, so a display that never edits looks as
// before.
//
// Free blocks have x/y (percent of the display) and s (scale, applied as the
// block's --display-zoom). y is the top edge; x is the block's anchor: its
// left edge, centre or right edge (BLOCK_ANCHORS), the side its content grows
// from in the default layout — so a longer lifter name or a wider weight
// never pushes a block off screen. The lights also have a gap between the
// three lights (#154), a factor on the default gap of layout.css; layouts
// and codes from before it get the default (1). The cards block (card colours and
// reasons under the lights) follows the lights: it only has a gap, in
// multiples of the light size. Every block can be hidden.
//
// The pause block (#163) came later: a layout or code without it gets a
// default pause block, so it stays valid. The stream overlay hides that
// default block (pauseHidden), because the stream shows other content during
// a pause; it can be shown in the editor.

export const LAYOUT_STORAGE_KEY = 'iron-verdict:display-layout';
// The stream overlay (OBS browser source) keeps its own layout, so opening the
// overlay in a browser that is also a hall display changes neither layout.
export const OVERLAY_LAYOUT_STORAGE_KEY = 'iron-verdict:display-layout:overlay';
export const FREE_BLOCKS = ['timer', 'lights', 'verdict', 'lifter', 'attempt', 'pause'];
export const LAYOUT_BLOCKS = [...FREE_BLOCKS, 'cards'];
export const BLOCK_ANCHORS = {
    timer: 'center', lights: 'center', verdict: 'center', lifter: 'left', attempt: 'right', pause: 'center',
};

const VERSION = 1;
const CODE_PREFIX = 'IV1.';
const X_MAX = 100;            // the anchor stays on screen
const Y_MAX = 99;             // the top edge stays on screen
const SCALE_MIN = 0.3;
const SCALE_MAX = 3;
const SCALE_STEP = 0.05;
const GAP_MAX = 2;
const GAP_STEP = 0.05;
// Below 0.4 the reasons of neighbouring lights touch (comparison matrix in #154).
const LIGHTS_GAP_MIN = 0.4;
const LIGHTS_GAP_MAX = 2;
const LIGHTS_GAP_DEFAULT = 1;
// Where a layout from before the pause block shows it: centred, at about the lights.
const PAUSE_DEFAULT = { x: 50, y: 30, s: 1 };

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
        x: clamp(x, 0, X_MAX),
        y: clamp(y, 0, Y_MAX),
        s: clamp(s, SCALE_MIN, SCALE_MAX),
        hidden: raw.hidden === true,
    };
}

function sanitizeLights(raw) {
    const block = sanitizeFree(raw);
    if (!block) return null;
    const gap = raw.gap === undefined ? LIGHTS_GAP_DEFAULT : raw.gap;
    if (!isNum(gap)) return null;
    return { ...block, gap: clamp(gap, LIGHTS_GAP_MIN, LIGHTS_GAP_MAX) };
}

function sanitizeCards(raw) {
    if (!raw || typeof raw !== 'object' || !isNum(raw.gap)) return null;
    return { gap: clamp(raw.gap, 0, GAP_MAX), hidden: raw.hidden === true };
}

function sanitizePause(raw, pauseHidden) {
    return raw === undefined ? { ...PAUSE_DEFAULT, hidden: pauseHidden } : sanitizeFree(raw);
}

// Returns a clean copy of a layout, or null if it is not a complete, known
// layout. Only numbers and booleans survive, so a stored or imported layout
// can never inject CSS into blockStyle(). pauseHidden: whether a missing pause
// block (layout from before #163) starts hidden.
export function sanitizeLayout(raw, { pauseHidden = false } = {}) {
    if (!raw || typeof raw !== 'object' || raw.v !== VERSION) return null;
    const src = raw.blocks;
    if (!src || typeof src !== 'object') return null;
    const blocks = {};
    for (const id of FREE_BLOCKS) {
        if (id === 'lights') blocks[id] = sanitizeLights(src[id]);
        else if (id === 'pause') blocks[id] = sanitizePause(src[id], pauseHidden);
        else blocks[id] = sanitizeFree(src[id]);
        if (!blocks[id]) return null;
    }
    blocks.cards = sanitizeCards(src.cards);
    if (!blocks.cards) return null;
    return { v: VERSION, blocks };
}

// storage may be null (localStorage blocked); loading then finds nothing and
// saving reports false, so the editor can say so.
export function loadLayout(storage, key = LAYOUT_STORAGE_KEY) {
    try {
        const raw = storage.getItem(key);
        return raw == null ? null : sanitizeLayout(JSON.parse(raw), { pauseHidden: key === OVERLAY_LAYOUT_STORAGE_KEY });
    } catch (_) {
        return null;
    }
}

export function saveLayout(storage, layout, key = LAYOUT_STORAGE_KEY) {
    try {
        storage.setItem(key, JSON.stringify(layout));
        return true;
    } catch (_) {
        return false;
    }
}

export function clearLayout(storage, key = LAYOUT_STORAGE_KEY) {
    try {
        storage.removeItem(key);
        return true;
    } catch (_) {
        return false;
    }
}

const ANCHOR_SHIFT = { left: '0', center: '-50%', right: '-100%' };

// x of a measured rect at the block's anchor.
function anchorX(rect, anchor) {
    if (anchor === 'left') return rect.left;
    if (anchor === 'right') return rect.right;
    return rect.left + rect.width / 2;
}

// A layout that puts every free block where it is now (rects from
// getBoundingClientRect), so leaving the flow layout does not move anything.
// pauseHidden: the pause block starts hidden (stream overlay).
export function layoutFromRects(root, rects, { pauseHidden = false } = {}) {
    const blocks = {};
    for (const id of FREE_BLOCKS) {
        const r = rects[id];
        blocks[id] = {
            x: tidy(((anchorX(r, BLOCK_ANCHORS[id]) - root.left) / root.width) * 100),
            y: tidy(((r.top - root.top) / root.height) * 100),
            s: 1,
            hidden: id === 'pause' && pauseHidden,
        };
    }
    blocks.lights.gap = LIGHTS_GAP_DEFAULT;
    blocks.cards = { gap: 0, hidden: false };
    return { v: VERSION, blocks };
}

// dx/dy in percent of the display; snaps to 1 %.
export function movedBlock(block, dx, dy) {
    return {
        ...block,
        x: clamp(Math.round(block.x + dx), 0, X_MAX),
        y: clamp(Math.round(block.y + dy), 0, Y_MAX),
    };
}

export function scaledBlock(block, ratio) {
    return { ...block, s: clamp(snap(block.s * ratio, SCALE_STEP), SCALE_MIN, SCALE_MAX) };
}

export function cardsWithGap(cards, gap) {
    return { ...cards, gap: clamp(snap(gap, GAP_STEP), 0, GAP_MAX) };
}

export function lightsWithGap(lights, gap) {
    return { ...lights, gap: clamp(snap(gap, GAP_STEP), LIGHTS_GAP_MIN, LIGHTS_GAP_MAX) };
}

export function withBlockHidden(layout, id, hidden) {
    return { ...layout, blocks: { ...layout.blocks, [id]: { ...layout.blocks[id], hidden } } };
}

// Inline style of a free block for Alpine's object :style. An object (not a
// string) so it leaves x-show's `display` alone; every key is always present,
// with '' for "unset" (no block = default flow layout), because Alpine only
// resets the keys of the next object.
export function blockStyle(block, anchor) {
    if (!block) return { left: '', top: '', transform: '', '--display-zoom': '' };
    return {
        left: `${block.x}%`,
        top: `${block.y}%`,
        transform: `translateX(${ANCHOR_SHIFT[anchor]})`,
        '--display-zoom': String(block.s),
    };
}

// Export code: "IV1." + base64url(JSON). Layouts hold only ASCII, so btoa is safe.
export function encodeLayout(layout) {
    const b64 = btoa(JSON.stringify(layout));
    return CODE_PREFIX + b64.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

export function decodeLayout(code, { pauseHidden = false } = {}) {
    const text = String(code || '').trim();
    if (!text.startsWith(CODE_PREFIX)) return null;
    const body = text.slice(CODE_PREFIX.length);
    if (!/^[A-Za-z0-9_-]+$/.test(body)) return null;
    try {
        const b64 = body.replace(/-/g, '+').replace(/_/g, '/');
        return sanitizeLayout(JSON.parse(atob(b64)), { pauseHidden });
    } catch (_) {
        return null;
    }
}
