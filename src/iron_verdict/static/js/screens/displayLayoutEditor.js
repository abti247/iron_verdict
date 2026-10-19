// Display layout editor, mixed into the display screen component: the saved
// layout of this device and the edit mode that changes it (drag, scale at the
// handle, hide, export/import code; Save/Cancel/Reset). The model and its
// rules live in displayLayout.js; this file only turns pointer input into
// layout changes. Nothing here touches the connection or the stores, so the
// display keeps showing votes, timer and VPortal data while editing.

import {
    loadLayout, saveLayout, clearLayout, layoutFromRects,
    movedBlock, scaledBlock, cardsWithGap, withBlockHidden, blockStyle,
    encodeLayout, decodeLayout, FREE_BLOCKS,
} from '../displayLayout.js';
import { t } from '../i18n.js';

const storage = () => window.localStorage;

export function displayLayoutEditor() {
    return {
        layout: null,           // saved layout of this device; null = default
        layoutDraft: null,      // layout being edited; null = default
        layoutEditing: false,
        layoutCodeOpen: false,
        layoutCodeInput: '',
        layoutCodeError: false,
        _layoutDrag: null,

        initDisplayLayout() {
            try { this.layout = loadLayout(storage()); } catch (_) { this.layout = null; }
            // Leaving the display (role select, session end) drops the draft.
            this.$watch('$store.nav.screen', (screen) => {
                if (screen !== 'display' && this.layoutEditing) this.cancelLayoutEdit();
            });
        },

        // What the display shows: the draft while editing, else the saved layout.
        activeLayout() {
            return this.layoutEditing ? this.layoutDraft : this.layout;
        },

        layoutBlockStyle(id) {
            const layout = this.activeLayout();
            const style = blockStyle(layout && layout.blocks[id]);
            if (id === 'lights') style['--orb-card-gap'] = layout ? String(layout.blocks.cards.gap) : '';
            return style;
        },

        layoutBlockHidden(id) {
            const layout = this.activeLayout();
            return !!(layout && layout.blocks[id].hidden);
        },

        // The VPortal corners while editing without a lifter: sample text so
        // they can be placed.
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
            this.displaySettingsOpen = false;
            this.layoutDraft = this.layout ? JSON.parse(JSON.stringify(this.layout)) : null;
            this.layoutCodeOpen = false;
            this.layoutCodeInput = '';
            this.layoutCodeError = false;
            this.layoutEditing = true;
        },

        saveLayoutEdit() {
            this.layout = this.layoutDraft;
            if (this.layout) saveLayout(storage(), this.layout);
            else clearLayout(storage());
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
            const layout = decodeLayout(this.layoutCodeInput);
            this.layoutCodeError = !layout;
            if (layout) this.layoutDraft = layout;
        },

        // mode: 'move' (free blocks), 'scale' (handle), 'gap' (cards block).
        layoutPointerDown(event, id, mode) {
            if (!this.layoutEditing || this._layoutDrag) return;
            event.preventDefault();
            const draft = this._materializeDraft();
            try { event.currentTarget.setPointerCapture(event.pointerId); } catch (_) {}
            const root = this.$root.getBoundingClientRect();
            const rect = this.$refs[`layout-${id === 'cards' ? 'lights' : id}`].getBoundingClientRect();
            this._layoutDrag = {
                id, mode,
                pointerId: event.pointerId,
                startX: event.clientX,
                startY: event.clientY,
                rootW: root.width,
                rootH: root.height,
                w: rect.width,
                h: rect.height,
                orb: this.$refs.layoutOrb.getBoundingClientRect().height,
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
                next = scaledBlock(d.block, Math.max((d.w + dx) / d.w, (d.h + dy) / d.h));
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
                this.layoutDraft = layoutFromRects(this.$root.getBoundingClientRect(), rects);
            }
            return this.layoutDraft;
        },

        _endLayoutEdit() {
            this.layoutEditing = false;
            this.layoutDraft = null;
            this._layoutDrag = null;
            this.layoutCodeOpen = false;
        },
    };
}
