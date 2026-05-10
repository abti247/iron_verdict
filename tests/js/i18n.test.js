import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { initI18n, t, setLanguage, getLanguage, getSupportedLanguages } from '../../src/iron_verdict/static/js/i18n.js';

const EN = { landing: { createSession: 'Create New Session' } };
const DE = { landing: { createSession: 'Neue Sitzung erstellen' } };

function mockFetch(enData = EN, deData = DE) {
    vi.stubGlobal('fetch', vi.fn((url) => {
        const data = url.includes('/en.json') ? enData : deData;
        return Promise.resolve({ json: () => Promise.resolve(data) });
    }));
}

/** Create a minimal localStorage stub for environments where the global lacks .clear() */
function makeLocalStorageStub() {
    const store = {};
    return {
        getItem: (k) => Object.prototype.hasOwnProperty.call(store, k) ? store[k] : null,
        setItem: (k, v) => { store[k] = String(v); },
        removeItem: (k) => { delete store[k]; },
        clear: () => { Object.keys(store).forEach(k => delete store[k]); },
        get length() { return Object.keys(store).length; },
        key: (i) => Object.keys(store)[i] ?? null,
    };
}

describe('i18n', () => {
    beforeEach(() => {
        vi.stubGlobal('localStorage', makeLocalStorageStub());
    });

    afterEach(() => {
        vi.unstubAllGlobals();
    });

    describe('t()', () => {
        it('resolves a dotted key in the active locale', async () => {
            mockFetch();
            await initI18n();
            expect(t('landing.createSession')).toBe('Create New Session');
        });

        it('falls back to English when key missing in active language', async () => {
            localStorage.setItem('iron-verdict-lang', 'de');
            mockFetch(EN, {}); // de fixture has no keys
            await initI18n();
            expect(t('landing.createSession')).toBe('Create New Session');
        });

        it('returns the key itself when missing from both locales', async () => {
            mockFetch({}, {}); // both fixtures empty
            await initI18n();
            expect(t('landing.createSession')).toBe('landing.createSession');
        });
    });

    // exercises resolveLanguage priority: localStorage > navigator > default
    describe('resolveLanguage (via getLanguage)', () => {
        it('localStorage value wins over navigator', () => {
            localStorage.setItem('iron-verdict-lang', 'de');
            vi.stubGlobal('navigator', { language: 'en-US' });
            expect(getLanguage()).toBe('de');
        });

        it('falls back to navigator language prefix when localStorage is empty', () => {
            vi.stubGlobal('navigator', { language: 'de-AT' });
            expect(getLanguage()).toBe('de');
        });

        it('falls back to "en" when neither localStorage nor navigator matches', () => {
            vi.stubGlobal('navigator', { language: 'fr-FR' });
            expect(getLanguage()).toBe('en');
        });
    });

    describe('setLanguage()', () => {
        it('persists to localStorage', () => {
            setLanguage('de');
            expect(localStorage.getItem('iron-verdict-lang')).toBe('de');
        });

        it('ignores unsupported languages', () => {
            localStorage.setItem('iron-verdict-lang', 'en');
            setLanguage('fr');
            expect(localStorage.getItem('iron-verdict-lang')).toBe('en');
        });
    });

    it('getSupportedLanguages returns ["en", "de"]', () => {
        expect(getSupportedLanguages()).toEqual(['en', 'de']);
    });
});
