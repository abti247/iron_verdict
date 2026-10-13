// Which screen is showing, registered as Alpine.store('nav'), and the browser
// history entry that goes with each screen change. Every screen component and
// connection.js navigate through it; the popstate handler (init.js) reads it.

export function createNavStore(history = window.history) {
    return {
        screen: 'landing',
        entryPath: '/',  // pathname the app was opened with; '/vportal' creates VPortal sessions
        handlingPopstate: false,  // set while following the browser's back/forward button
        navigateInPlaceNext: false,  // one-shot, see navigateTo

        navigateTo(screen) {
            if (this.screen === screen) return;
            this.screen = screen;
            if (this.handlingPopstate) return;
            if (this.navigateInPlaceNext) {
                // One-shot: rehydrating state after a reload — keep the back-stack the same
                // depth as it was before the reload so mobile swipe-back keeps working.
                this.navigateInPlaceNext = false;
                history.replaceState({ screen }, '', '/');
            } else {
                history.pushState({ screen }, '', '/');
            }
        },
    };
}
