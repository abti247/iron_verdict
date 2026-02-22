import { ironVerdictApp } from './app.js';

// Read demo join params from URL before Alpine loads.
// Demo popup URLs contain ?code=&demo= so Alpine's init() can auto-join.
// These params only ever appear in demo sessions (not real competitions),
// so no sensitive data is exposed.
(function () {
    var p = new URLSearchParams(window.location.search);
    var code = p.get('code');
    var demo = p.get('demo');
    window._demoParams = (code && demo) ? { code: code, demo: demo } : null;
})();

document.addEventListener('alpine:init', () => {
    Alpine.data('ironVerdictApp', ironVerdictApp);
});

// Handle browser back button
window.addEventListener('popstate', () => {
    const appElement = document.querySelector('[x-data]');
    if (appElement && appElement.__x_data) {
        const app = appElement.__x_data;
        if ((app.screen === 'judge' || app.screen === 'display') && app.sessionCode) {
            app.returnToRoleSelection();
            // Prevent default back navigation
            history.pushState(null, null, location.href);
        }
    }
});
