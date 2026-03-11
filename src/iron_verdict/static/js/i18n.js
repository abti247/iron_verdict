/**
 * i18n module — language resolution, translation lookup, Alpine store integration.
 *
 * Usage:
 *   import { initI18n, t, setLanguage, getLanguage } from './i18n.js';
 *   await initI18n();            // call once at startup
 *   t('landing.createSession')   // → "Create New Session" or "Neue Sitzung erstellen"
 *   setLanguage('de');           // switches language, triggers Alpine re-render
 */

const SUPPORTED_LANGS = ['en', 'de'];
const DEFAULT_LANG = 'en';
const STORAGE_KEY = 'iron-verdict-lang';

/** Loaded locale data: { en: {...}, de: {...} } */
const locales = {};

/**
 * Resolve initial language from localStorage → navigator.language → default.
 */
function resolveLanguage() {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored && SUPPORTED_LANGS.includes(stored)) return stored;

    const browserLang = (navigator.language || '').split('-')[0].toLowerCase();
    if (SUPPORTED_LANGS.includes(browserLang)) return browserLang;

    return DEFAULT_LANG;
}

/**
 * Traverse a nested object by dotted key path.
 * resolve({a: {b: 'hello'}}, 'a.b') → 'hello'
 */
function resolve(obj, keyPath) {
    return keyPath.split('.').reduce((acc, part) => acc?.[part], obj);
}

/**
 * Load all locale JSON files. Call once at startup.
 */
export async function initI18n() {
    const results = await Promise.all(
        SUPPORTED_LANGS.map(lang =>
            fetch(`/static/locales/${lang}.json`).then(r => r.json())
        )
    );
    SUPPORTED_LANGS.forEach((lang, i) => { locales[lang] = results[i]; });

    const lang = resolveLanguage();
    document.documentElement.lang = lang;

    // Alpine store will be created in init.js after Alpine is ready
    return lang;
}

/**
 * Look up a translation key against the current language.
 * Falls back to English if key is missing in current language.
 */
export function t(key) {
    const lang = typeof Alpine !== 'undefined' && Alpine.store('i18n')
        ? Alpine.store('i18n').lang
        : resolveLanguage();
    return resolve(locales[lang], key) ?? resolve(locales[DEFAULT_LANG], key) ?? key;
}

/**
 * Switch language, persist to localStorage, update Alpine store + html lang.
 */
export function setLanguage(lang) {
    if (!SUPPORTED_LANGS.includes(lang)) return;
    localStorage.setItem(STORAGE_KEY, lang);
    document.documentElement.lang = lang;
    if (typeof Alpine !== 'undefined' && Alpine.store('i18n')) {
        Alpine.store('i18n').lang = lang;
    }
}

/**
 * Return current language code.
 */
export function getLanguage() {
    if (typeof Alpine !== 'undefined' && Alpine.store('i18n')) {
        return Alpine.store('i18n').lang;
    }
    return resolveLanguage();
}

/**
 * Return list of supported language codes.
 */
export function getSupportedLanguages() {
    return SUPPORTED_LANGS;
}
