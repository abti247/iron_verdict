// Bootstrap: registers the stores and screen components with Alpine, wires them
// to the one connection (connection.js) and picks the first screen.

import { createSessionStore } from './sessionStore.js';
import { createNavStore } from './navigation.js';
import { createSettingsStore } from './settingsStore.js';
import { createTimerStore } from './timer.js';
import { createJudgeStore } from './judgeStore.js';
import { createDisplayStore } from './displayStore.js';
import { createVportalStore } from './vportalStore.js';
import { createPauseStore } from './pauseStore.js';
import { createConnection } from './connection.js';
import { landingScreen } from './screens/landingScreen.js';
import { contactScreen } from './screens/contactScreen.js';
import { demoIntroScreen } from './screens/demoIntroScreen.js';
import { reconnectingScreen } from './screens/reconnectingScreen.js';
import { roleSelectScreen } from './screens/roleSelectScreen.js';
import { judgeScreen } from './screens/judgeScreen.js';
import { displayScreen } from './screens/displayScreen.js';

// Called on alpine:init, before Alpine renders anything. Returns the connection.
export function registerApp(Alpine, { lang = 'en', demoParams = null, overlayParams = null } = {}) {
    Alpine.store('i18n', { lang, _v: 0 });  // t() reads it, setLanguage() writes it
    Alpine.store('session', createSessionStore());
    Alpine.store('nav', createNavStore());
    Alpine.store('settings', createSettingsStore());
    Alpine.store('timer', createTimerStore());
    Alpine.store('display', createDisplayStore());
    Alpine.store('vportal', createVportalStore());
    Alpine.store('pause', createPauseStore());

    let conn = null;
    Alpine.store('judge', createJudgeStore({
        session: Alpine.store('session'),
        settings: Alpine.store('settings'),
        send: (data) => conn.send(data),
    }));

    const store = (name) => Alpine.store(name);
    conn = createConnection({
        stores: {
            session: store('session'),
            nav: store('nav'),
            judge: store('judge'),
            display: store('display'),
            timer: store('timer'),
            settings: store('settings'),
            vportal: store('vportal'),
            pause: store('pause'),
        },
    });

    Alpine.data('landingScreen', () => landingScreen(conn));
    Alpine.data('contactScreen', () => contactScreen());
    Alpine.data('demoIntroScreen', () => demoIntroScreen());
    Alpine.data('reconnectingScreen', () => reconnectingScreen(conn));
    Alpine.data('roleSelectScreen', () => roleSelectScreen(conn));
    Alpine.data('judgeScreen', () => judgeScreen(conn));
    Alpine.data('displayScreen', () => displayScreen(conn));

    // Capture URL params and pathname before scrubbing them via replaceState.
    // The stream overlay keeps its URL: OBS reloads the current URL, which must
    // still name the session and the overlay.
    const urlSession = new URLSearchParams(window.location.search).get('session');
    Alpine.store('nav').entryPath = window.location.pathname;
    if (overlayParams) {
        history.replaceState({ screen: 'display' }, '');
    } else {
        history.replaceState({ screen: 'landing' }, '', '/');
    }
    conn.start({ urlSession, overlayParams, demoParams });
    return conn;
}
