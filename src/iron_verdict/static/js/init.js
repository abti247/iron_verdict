import { registerApp } from './app.js';
import { initI18n, t, setLanguage, getLanguage } from './i18n.js';

// Read demo and stream-overlay join params from URL before Alpine loads.
(function () {
    var p = new URLSearchParams(window.location.search);
    var code = p.get('code');
    var demo = p.get('demo');
    window._demoParams = (code && demo) ? { code: code, demo: demo } : null;
    // Stream overlay (OBS browser source): ?session=CODE&overlay=1[&layout=IV1…].
    // The class makes the page transparent from the boot screen on, so a reload
    // in OBS never flashes a dark full screen over the video.
    var overlay = p.get('overlay') === '1';
    window._overlayParams = overlay ? { code: p.get('session') || '', layoutCode: p.get('layout') || '' } : null;
    if (overlay) document.documentElement.classList.add('display-overlay');
})();

// Wait for translations + custom fonts, then load Alpine. Alpine's CDN build
// (vendored, served same-origin) auto-starts on script load, so deferring the
// load itself is what guarantees the first render uses the right strings in the
// right font. The fonts are self-hosted, so this wait is a few milliseconds and
// does not depend on the internet; a failed font still lets Alpine start.
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
    s.src = '/static/vendor/alpinejs-3.14.1.min.js';
    // Show the "could not be loaded" message now instead of after the
    // boot.css timeout — this download failing means Alpine will never start.
    s.onerror = () => document.documentElement.classList.add('boot-failed');
    document.head.appendChild(s);
});

// Leave the boot state (boot.css) once Alpine has rendered the first screen.
document.addEventListener('alpine:initialized', () => {
    document.documentElement.classList.remove('booting', 'boot-failed');
});

// Expose t, setLanguage, getLanguage as globals for Alpine template expressions
window.t = t;
window.setLanguage = setLanguage;
window.getLanguage = getLanguage;

let app = null;  // the connection, once Alpine has started (app.js)

document.addEventListener('alpine:init', () => {
    const demoParams = window._demoParams;
    const overlayParams = window._overlayParams;
    window._demoParams = null;
    window._overlayParams = null;
    app = registerApp(Alpine, { lang: window._resolvedLang || 'en', demoParams, overlayParams });
});

// Handle browser back button — navigate within the screen machine.
window.addEventListener('popstate', (event) => {
    if (!app) return;
    app.followHistory(event.state?.screen ?? 'landing');
});
