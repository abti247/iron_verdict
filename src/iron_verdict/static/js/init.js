import { ironVerdictApp } from './app.js';
import { initI18n, t, setLanguage, getLanguage } from './i18n.js';

// Read demo join params from URL before Alpine loads.
(function () {
    var p = new URLSearchParams(window.location.search);
    var code = p.get('code');
    var demo = p.get('demo');
    window._demoParams = (code && demo) ? { code: code, demo: demo } : null;
})();

// Wait for translations + custom fonts, then load Alpine. Alpine's CDN build
// auto-starts on script load, so deferring the load itself is what guarantees
// the first render uses the right strings in the right font.
// document.fonts.load() explicitly requests each face — browsers skip loading
// fonts for display:none elements (x-cloak), so without this we'd never trigger
// the fetches before Alpine renders.
const loadFont = (spec) => document.fonts.load(spec).catch(() => null);
Promise.all([
    initI18n(),
    loadFont('1em "Bebas Neue"'),
    loadFont('400 1em "Rajdhani"'),
    loadFont('600 1em "Rajdhani"'),
    loadFont('700 1em "Rajdhani"'),
]).then(([lang]) => {
    window._resolvedLang = lang;
    const s = document.createElement('script');
    s.src = 'https://cdn.jsdelivr.net/npm/alpinejs@3.14.1/dist/cdn.min.js';
    s.integrity = 'sha384-l8f0VcPi/M1iHPv8egOnY/15TDwqgbOR1anMIJWvU6nLRgZVLTLSaNqi/TOoT5Fh';
    s.crossOrigin = 'anonymous';
    document.head.appendChild(s);
});

// Expose as global so Alpine can call ironVerdictApp()
window.ironVerdictApp = ironVerdictApp;

// Expose t, setLanguage, getLanguage as globals for Alpine template expressions
window.t = t;
window.setLanguage = setLanguage;
window.getLanguage = getLanguage;

document.addEventListener('alpine:init', () => {
    // Create reactive i18n store — t() reads from this, setLanguage() writes to it
    Alpine.store('i18n', { lang: window._resolvedLang || 'en', _v: 0 });
    Alpine.data('ironVerdictApp', ironVerdictApp);
});

// Handle browser back button — navigate within the screen machine.
window.addEventListener('popstate', (event) => {
    const appElement = document.querySelector('[x-data]');
    if (!appElement || !window.Alpine) return;
    const app = Alpine.$data(appElement);
    if (!app) return;

    const target = event.state?.screen ?? 'landing';
    app._handlingPopstate = true;
    try {
        if (target === 'role-select') {
            app.returnToRoleSelection();
        } else if (target === 'landing') {
            app.returnToLanding();
        } else {
            app.screen = target;
        }
    } finally {
        app._handlingPopstate = false;
    }
});
