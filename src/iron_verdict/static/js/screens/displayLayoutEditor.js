// Display layout editor, mixed into the display screen component: the saved
// layout of this device and the edit mode that changes it (drag, scale at the
// handle, hide, export/import code; Save/Cancel/Reset). The model and its
// rules live in displayLayout.js; this file only turns pointer input into
// layout changes. Nothing here touches the connection or the stores, so the
// display keeps showing votes, timer and VPortal data while editing.
//
// The pause (#163) never shows together with timer, lights, verdict and
// lifter, and in the default layout both sit in the middle; so the editor has
// two views (layoutView): the lift blocks or the pause block. The blocks of
// the other view stay in the page, invisible (layout-off-view), so they can
// still be measured when the draft leaves the default layout.
//
// The stream overlay stores its layout under its own key; a layout code in its
// URL (&layout=…) is then the only source and the edit mode stays closed, so a
// reload in OBS never brings back something other than what was edited.

import {
    loadLayout, saveLayout, clearLayout, layoutFromRects,
    movedBlock, scaledBlock, cardsWithGap, lightsWithGap, withBlockHidden, blockStyle,
    encodeLayout, decodeLayout, FREE_BLOCKS, BLOCK_ANCHORS,
    LAYOUT_STORAGE_KEY, OVERLAY_LAYOUT_STORAGE_KEY,
} from '../displayLayout.js';
import { t } from '../i18n.js';

// null when the browser blocks site data; load/save then report it.
function storage() {
    try { return window.localStorage; } catch (_) { return null; }
}

export function displayLayoutEditor() {
    return {
        layout: null,           // saved layout of this device; null = default
        layoutDraft: null,      // layout being edited; null = default
        layoutEditing: false,
        layoutView: 'lift',     // 'lift' | 'pause': which blocks the editor shows
        layoutCodeOpen: false,
        layoutCodeInput: '',
        layoutCodeError: false,
        layoutSaveError: false,
        layoutFromUrl: false,   // stream overlay: the layout comes from its URL, no editing
        layoutUrlInvalid: false, // stream overlay: the URL's layout code could not be read
        _layoutKey: LAYOUT_STORAGE_KEY,
        _layoutDrag: null,

        initDisplayLayout() {
            const session = this.$store.session;
            this._layoutKey = session.overlay ? OVERLAY_LAYOUT_STORAGE_KEY : LAYOUT_STORAGE_KEY;
            const urlLayout = session.overlay && session.overlayLayoutCode
                ? decodeLayout(session.overlayLayoutCode, { pauseHidden: true }) : null;
            this.layoutFromUrl = !!urlLayout;
            this.layoutUrlInvalid = !!(session.overlay && session.overlayLayoutCode && !urlLayout);
            this.layout = urlLayout || loadLayout(storage(), this._layoutKey);
            // Leaving the display (role select, session end) drops the draft.
            this.$watch('$store.nav.screen', (screen) => {
                if (screen !== 'display' && this.layoutEditing) this.cancelLayoutEdit();
            });
        },

        // Whether block id belongs to the editor view that is not shown.
        layoutOffView(id) {
            return this.layoutEditing && (id === 'pause') !== (this.layoutView === 'pause');
        },

        toggleLayoutView() {
            this.layoutView = this.layoutView === 'pause' ? 'lift' : 'pause';
        },

        // What the display shows: the draft while editing, else the saved layout.
        activeLayout() {
            return this.layoutEditing ? this.layoutDraft : this.layout;
        },

        layoutBlockStyle(id) {
            const layout = this.activeLayout();
            const style = blockStyle(layout && layout.blocks[id], BLOCK_ANCHORS[id]);
            if (id === 'lights') {
                style['--orb-card-gap'] = layout ? String(layout.blocks.cards.gap) : '';
                style['--lights-gap'] = layout ? String(layout.blocks.lights.gap) : '';
            }
            return style;
        },

        // Without a layout every block shows, except the pause block in the
        // stream overlay (the stream shows other content during a pause, #163).
        layoutBlockHidden(id) {
            const layout = this.activeLayout();
            if (!layout) return id === 'pause' && this._pauseHiddenByDefault();
            return layout.blocks[id].hidden;
        },

        _pauseHiddenByDefault() {
            return !!this.$store.session.overlay;
        },

        // The VPortal corners while editing without a lifter: sample text so
        // they can be placed, faded and labelled as a sample (cornerIsSample).
        cornerIsSample() {
            return this.layoutEditing && !this.$store.vportal.displayAttempt;
        },

        cornerAttempt() {
            const attempt = this.$store.vportal.displayAttempt;
            if (attempt || !this.layoutEditing) return attempt;
            return {
                firstName: t('displayLayout.sample.firstName'),
                lastName: t('displayLayout.sample.lastName'),
                club: t('displayLayout.sample.club'),
                bodyWeightCategory: t('displayLayout.sample.bodyWeightCategory'),
                ageCategory: t('displayLayout.sample.ageCategory'),
                discipline: t('displayLayout.sample.discipline'),
                attempt: 1,
                weight: 200,
            };
        },

        startLayoutEdit() {
            if (this.layoutFromUrl) return;
            this.displaySettingsOpen = false;
            this.layoutDraft = this.layout ? JSON.parse(JSON.stringify(this.layout)) : null;
            this.layoutCodeOpen = false;
            this.layoutCodeInput = '';
            this.layoutCodeError = false;
            this.layoutSaveError = false;
            // A running pause is what the hall sees now: start with its view.
            this.layoutView = this.$store.pause.active ? 'pause' : 'lift';
            this.layoutEditing = true;
        },

        // If this device cannot store it, the editor stays open with a message:
        // the layout would be gone after the next reload.
        saveLayoutEdit() {
            const draft = this.layoutDraft;
            const stored = draft
                ? saveLayout(storage(), draft, this._layoutKey)
                : clearLayout(storage(), this._layoutKey);
            this.layoutSaveError = !stored;
            if (!stored) return;
            this.layout = draft;
            this._endLayoutEdit();
        },

        cancelLayoutEdit() {
            this._endLayoutEdit();
        },

        // Back to the default flow layout; stored only with "Save".
        resetLayoutEdit() {
            this.layoutDraft = null;
            this.layoutCodeError = false;
        },

        toggleLayoutBlockHidden(id) {
            const draft = this._materializeDraft();
            this.layoutDraft = withBlockHidden(draft, id, !draft.blocks[id].hidden);
        },

        layoutExportCode() {
            return this.layoutDraft ? encodeLayout(this.layoutDraft) : '';
        },

        applyLayoutCode() {
            const layout = decodeLayout(this.layoutCodeInput, { pauseHidden: this._pauseHiddenByDefault() });
            this.layoutCodeError = !layout;
            if (layout) this.layoutDraft = layout;
        },

        // mode: 'move' (free blocks), 'scale' (handle), 'gap' (cards block),
        // 'lightsGap' (side handle of the lights).
        layoutPointerDown(event, id, mode) {
            if (!this.layoutEditing || this._layoutDrag) return;
            event.preventDefault();
            const draft = this._materializeDraft();
            try { event.currentTarget.setPointerCapture(event.pointerId); } catch (_) {}
            const root = this.$root.getBoundingClientRect();
            const rect = this.$refs[`layout-${id === 'cards' ? 'lights' : id}`].getBoundingClientRect();
            const anchor = BLOCK_ANCHORS[id];
            this._layoutDrag = {
                id, mode,
                pointerId: event.pointerId,
                startX: event.clientX,
                startY: event.clientY,
                rootW: root.width,
                rootH: root.height,
                // Scaling keeps the anchor (left edge, centre or right edge) in place.
                anchorX: anchor === 'left' ? rect.left : anchor === 'right' ? rect.right : rect.left + rect.width / 2,
                h: rect.height,
                orb: this.$refs.layoutOrb.getBoundingClientRect().height,
                // The lights are centred, so the side handle moves by as much
                // as the gap changes.
                columnGap: parseFloat(getComputedStyle(this.$refs['layout-lights']).columnGap),
                block: draft.blocks[id],
            };
        },

        layoutPointerMove(event) {
            const d = this._layoutDrag;
            if (!d || event.pointerId !== d.pointerId) return;
            const dx = event.clientX - d.startX;
            const dy = event.clientY - d.startY;
            let next;
            if (d.mode === 'move') {
                next = movedBlock(d.block, (dx / d.rootW) * 100, (dy / d.rootH) * 100);
            } else if (d.mode === 'scale') {
                const fromAnchor = d.startX - d.anchorX;
                const rx = Math.abs(fromAnchor) >= 1 ? (event.clientX - d.anchorX) / fromAnchor : 0;
                next = scaledBlock(d.block, Math.max(rx, (d.h + dy) / d.h));
            } else if (d.mode === 'lightsGap') {
                next = lightsWithGap(d.block, d.block.gap * (d.columnGap + dx) / d.columnGap);
            } else {
                next = cardsWithGap(d.block, d.block.gap + dy / d.orb);
            }
            this.layoutDraft = {
                ...this.layoutDraft,
                blocks: { ...this.layoutDraft.blocks, [d.id]: next },
            };
        },

        layoutPointerUp(event) {
            if (this._layoutDrag && event.pointerId === this._layoutDrag.pointerId) {
                this._layoutDrag = null;
            }
        },

        // The default layout has no positions: measure where the blocks are
        // now, so the first change does not move anything else.
        _materializeDraft() {
            if (!this.layoutDraft) {
                const rects = {};
                for (const id of FREE_BLOCKS) rects[id] = this.$refs[`layout-${id}`].getBoundingClientRect();
                this.layoutDraft = layoutFromRects(this.$root.getBoundingClientRect(), rects, {
                    pauseHidden: this._pauseHiddenByDefault(),
                });
            }
            return this.layoutDraft;
        },

        _endLayoutEdit() {
            this.layoutEditing = false;
            this.layoutSaveError = false;
            this.layoutDraft = null;
            this._layoutDrag = null;
            this.layoutCodeOpen = false;
        },
    };
}
