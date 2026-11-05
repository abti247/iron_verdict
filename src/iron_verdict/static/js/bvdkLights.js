// Stream overlay lights (#215): the BVDK view (a box with head "REFEREES" and
// the discipline, three square lights and one row per invalid vote) or Iron
// Verdict Classic (the round lights of the hall display). Pure functions only;
// screens/displayBvdk.js drives them. The choice is kept per device
// (localStorage) and never goes over the network; without one, or when site
// data is blocked, the overlay shows the BVDK view.

import { BVDK_DISCIPLINES } from './constants.js';
import { lightColor, cardColor } from './voteLight.js';

export const LIGHTS_VIEW_STORAGE_KEY = 'iron-verdict:overlay-lights-view';
export const LIGHTS_VIEWS = ['bvdk', 'classic'];
const DEFAULT_VIEW = 'bvdk';
const POSITIONS = ['left', 'center', 'right'];

// What the BVDK box shows for a result of the display store. Reasons are the
// translated labels; they stay plain text (rendered with x-text only).
export function bvdkResult({ votes, reasons, showExplanations, liftType }) {
    const lights = POSITIONS.map((pos) => ({ pos, red: lightColor(votes[pos]) === 'red' }));
    const rows = [];
    POSITIONS.forEach((pos, index) => {
        const card = cardColor(votes[pos]);
        if (!card) return;
        const reason = showExplanations && reasons && reasons[pos] ? String(reasons[pos]) : '';
        rows.push({ pos, index, card, reason });
    });
    return { lights, rows, discipline: BVDK_DISCIPLINES[liftType] || '' };
}

// storage may be null (localStorage blocked).
export function loadLightsView(storage) {
    try {
        const value = storage.getItem(LIGHTS_VIEW_STORAGE_KEY);
        return LIGHTS_VIEWS.includes(value) ? value : DEFAULT_VIEW;
    } catch (_) {
        return DEFAULT_VIEW;
    }
}

export function saveLightsView(storage, view) {
    try {
        storage.setItem(LIGHTS_VIEW_STORAGE_KEY, view);
        return true;
    } catch (_) {
        return false;
    }
}
