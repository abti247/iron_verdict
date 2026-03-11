import { ironVerdictApp } from './app.js';
import { initI18n, t, setLanguage, getLanguage } from './i18n.js';

// Read demo join params from URL before Alpine loads.
(function () {
    var p = new URLSearchParams(window.location.search);
    var code = p.get('code');
    var demo = p.get('demo');
    window._demoParams = (code && demo) ? { code: code, demo: demo } : null;
})();

// Load locale files before Alpine starts
initI18n().then(lang => {
    window._resolvedLang = lang;
    // If Alpine already created the store, update it and bump _v to trigger re-render
    if (typeof Alpine !== 'undefined' && Alpine.store('i18n')) {
        Alpine.store('i18n').lang = lang;
        Alpine.store('i18n')._v++;
    }
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

// Handle browser back button
window.addEventListener('popstate', () => {
    const appElement = document.querySelector('[x-data]');
    if (appElement && appElement.__x_data) {
        const app = appElement.__x_data;
        if ((app.screen === 'judge' || app.screen === 'display') && app.sessionCode) {
            app.returnToRoleSelection();
            history.pushState(null, null, location.href);
        }
    }
});
