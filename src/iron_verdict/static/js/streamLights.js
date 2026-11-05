// How long the stream overlay shows the lights after a decision (#216):
// "always" (the hall display's behaviour: visible until the next lift) or
// 3 to 15 seconds. Pure functions only; screens/displayStreamLights.js drives
// it. Kept per device (localStorage), never over the network; without a
// choice, or when site data is blocked, the overlay shows them for 5 seconds.

export const LIGHTS_DURATION_STORAGE_KEY = 'iron-verdict:overlay-lights-duration';
const MIN_SECONDS = 3;
const MAX_SECONDS = 15;
const DEFAULT_DURATION = 5;
export const LIGHTS_DURATIONS = ['always', ...Array.from(
    { length: MAX_SECONDS - MIN_SECONDS + 1 }, (_, i) => MIN_SECONDS + i,
)];

// storage may be null (localStorage blocked).
export function loadLightsDuration(storage) {
    try {
        const value = storage.getItem(LIGHTS_DURATION_STORAGE_KEY);
        if (value === 'always') return 'always';
        const seconds = Number(value);
        return value !== null && LIGHTS_DURATIONS.includes(seconds) ? seconds : DEFAULT_DURATION;
    } catch (_) {
        return DEFAULT_DURATION;
    }
}

export function saveLightsDuration(storage, duration) {
    try {
        storage.setItem(LIGHTS_DURATION_STORAGE_KEY, String(duration));
        return true;
    } catch (_) {
        return false;
    }
}
