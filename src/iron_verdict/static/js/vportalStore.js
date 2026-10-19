// VPortal state for the whole page, registered as Alpine.store('vportal'):
// connect button and dialog on role-select, lifter overlay on the display.
// A store rather than a component because these three live in separate places
// of the markup but share one connection. The main component (app.js) only
// hands in session info and starts the display overlay.

import { vportalClient } from './vportalClient.js';
import { vportalLoginErrorMessage } from './vportalErrors.js';
import { t as translate } from './i18n.js';

export function createVportalStore({
    client = vportalClient,
    t = translate,
    fetchFn = (...args) => fetch(...args),
} = {}) {
    return {
        stagingAvailable: false,
        connected: false,
        stageName: '',
        federationLabel: '',
        modalOpen: false,
        modalStep: 'federation',
        loginError: '',
        stageError: '',
        federation: 'BVDK',
        identity: '',
        credential: '',
        stages: [],
        selectedStage: '',
        displayAttempt: null,
        disconnectedReason: '',
        // Bumped when the user connects or disconnects in the dialog; the display
        // screen then has the connection restart the overlay (stream overlay, #107).
        loginChanges: 0,
        _pollStop: null,
        _retryTimer: null,
        _displayRun: 0,  // bumped on every stop; a lookup from an older run must not start a poller

        openModal() {
            this.modalOpen = true;
            this.modalStep = this.connected ? 'connected' : 'federation';
        },

        async doLogin(sessionCode) {
            this.loginError = '';
            this.stageError = '';
            // Clear a previous connect's stage list so a failed or still-running
            // fetch never shows stale stages as selectable.
            this.stages = [];
            this.selectedStage = '';
            const host = this._hostForFederation(this.federation);
            try {
                await client.login(sessionCode, host, this.identity, this.credential);
            } catch (err) {
                this.loginError = vportalLoginErrorMessage(err, t);
                return;
            }
            this.federationLabel = this.federation;
            this.modalStep = 'stage';
            // A failure here must show on the stage step: the credentials step
            // (and its error line) is already hidden.
            try {
                this.stages = await client.fetchStages(sessionCode);
            } catch (err) {
                console.warn('vportal stage list failed', err);
                this.stageError = t('vportal.errorStagesFailed');
                return;
            }
            if (this.stages.length > 0) {
                this.selectedStage = this.stages[0].id;
            }
        },

        confirmStage(sessionCode) {
            const stage = this.stages.find(s => s.id === this.selectedStage);
            client.setStage(sessionCode, stage.id, stage.name);
            this.stageName = stage.name;
            this.connected = true;
            this.modalOpen = false;
            this.loginChanges += 1;
        },

        disconnect(sessionCode) {
            client.logout(sessionCode);
            this.connected = false;
            this.stageName = '';
            this.modalOpen = false;
            this.loginChanges += 1;
        },

        _hostForFederation(fed) {
            // Test-only override: any test that sets window._testVportalHost gets routed to the fake server.
            if (window._testVportalHost) return window._testVportalHost;
            if (fed === 'BVDK') return 'bvdk.vportal-online.de';
            if (fed === 'OEVK') return 'oevk.vportal-online.de';
            if (fed === 'BVDK_STAGING') return 'staging-bvdk.vportal-online.de';
            return 'bvdk.vportal-online.de';
        },

        _federationForHost(host) {
            if (host === 'oevk.vportal-online.de') return 'OEVK';
            if (host === 'staging-bvdk.vportal-online.de') return 'BVDK_STAGING';
            return 'BVDK';
        },

        // Session lookup result (`GET /api/sessions/{code}`), or null if it could not be read.
        applySessionInfo(info) {
            this.stagingAvailable = !!info?.staging_available;
        },

        // Pick up server-side flags (staging_available) for a freshly-created session.
        async loadStagingFlag(sessionCode) {
            try {
                const lookup = await fetchFn(`/api/sessions/${sessionCode}`);
                if (lookup.ok) {
                    const info = await lookup.json();
                    this.stagingAvailable = !!info.staging_available;
                }
            } catch (_e) { /* swallow — modal will just hide the staging option */ }
        },

        // Called when this device joins as display. Resolves with the session kind
        // from the server, or null if the lookup failed and is not retried (the
        // caller keeps its own kind then). If the display is left meanwhile it
        // resolves with null or, during a retry wait, never settles.
        // streamOverlay (OBS browser source, #107): its panel offers the connect
        // dialog only once the kind is known, so a failed lookup is retried even
        // without a login (no banner then: nothing is missing yet), and a login
        // stored before a reload shows as connected.
        async startDisplayOverlay(sessionCode, { streamOverlay = false } = {}) {
            // Never two pollers: a restart replaces whatever the last start left running.
            this.stopDisplayOverlay();
            const run = this._displayRun;
            for (;;) {
                // Authoritative kind check — the caller's session kind may be stale after reload-recovery
                // because role-select didn't run on this page lifetime.
                const data = await this._lookupSession(sessionCode);
                if (run !== this._displayRun) return null;
                if (data) {
                    const kind = data.kind || 'generic';
                    this.stagingAvailable = !!data.staging_available;
                    if (kind === 'vportal') {
                        if (streamOverlay) this._showStoredLogin(sessionCode);
                        this._startPolling(sessionCode);
                    } else this.disconnectedReason = '';
                    return kind;
                }
                // Without its own VPortal login a hall display never polls, so there is
                // nothing to retry for; the stream overlay still needs the kind (see above).
                const stored = this._pollableStored(sessionCode);
                if (!stored && !streamOverlay) return null;
                if (stored) {
                    // Show the real state: the lifter data is missing until the lookup succeeds.
                    this.displayAttempt = null;
                    this.disconnectedReason = 'session-lookup-failed';
                }
                // Retry interval, not an artificial delay: the same pace as the VPortal
                // polling this lookup unlocks (the stream overlay without a login: the
                // default polling interval until its connect button can show), so a
                // reloaded display on a flaky network recovers without a second reload
                // and without hammering our server.
                await new Promise((resolve) => {
                    this._retryTimer = setTimeout(resolve, stored?.fetch_interval_ms || 3000);
                });
                if (run !== this._displayRun) return null;
            }
        },

        // Called when this device leaves the display (role-select, landing, session end).
        stopDisplayOverlay() {
            this._displayRun += 1;
            clearTimeout(this._retryTimer);
            this._retryTimer = null;
            if (this._pollStop) this._pollStop();
            this._pollStop = null;
            this.displayAttempt = null;
            this.disconnectedReason = '';
        },

        // Session lookup result (`GET /api/sessions/{code}`), or null on a network error or non-2xx.
        async _lookupSession(sessionCode) {
            try {
                const resp = await fetchFn(`/api/sessions/${sessionCode}`);
                if (!resp.ok) return null;
                return await resp.json();
            } catch (_e) {
                return null;
            }
        },

        // This device's stored VPortal login if it can poll (logged in, stage chosen), else null.
        _pollableStored(sessionCode) {
            if (!client.isConnected(sessionCode)) return null;
            const stored = client.getStored(sessionCode);
            return stored?.stage_id ? stored : null;
        },

        // A login stored before a reload shows as connected, so the dialog opened
        // from the stream overlay's panel does not ask for it again. Only for the
        // overlay: its URL never changes session, so this cannot go stale; the
        // hall display keeps the state of its own connect dialog.
        _showStoredLogin(sessionCode) {
            const stored = this._pollableStored(sessionCode);
            if (!stored) return;
            this.connected = true;
            this.stageName = stored.stage_name || '';
            this.federationLabel = this._federationForHost(stored.host);
        },

        _startPolling(sessionCode) {
            const stored = this._pollableStored(sessionCode);
            if (!stored) return;
            // A poll already in flight when the display is left still reports back; it must
            // not overwrite the next run's state.
            const run = this._displayRun;
            this._pollStop = client.pollActiveAttempt(
                sessionCode,
                stored.fetch_interval_ms || 3000,
                (attempt) => {
                    if (run !== this._displayRun) return;
                    if (attempt && attempt.__stale) {
                        return;
                    }
                    this.displayAttempt = attempt;
                    this.disconnectedReason = '';
                },
                (kind) => {
                    if (run !== this._displayRun) return;
                    this.displayAttempt = null;
                    this.disconnectedReason = kind;
                },
            );
        },
    };
}
