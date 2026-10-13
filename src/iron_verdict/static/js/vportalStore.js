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
        _pollStop: null,

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
        },

        disconnect(sessionCode) {
            client.logout(sessionCode);
            this.connected = false;
            this.stageName = '';
            this.modalOpen = false;
        },

        _hostForFederation(fed) {
            // Test-only override: any test that sets window._testVportalHost gets routed to the fake server.
            if (window._testVportalHost) return window._testVportalHost;
            if (fed === 'BVDK') return 'bvdk.vportal-online.de';
            if (fed === 'OEVK') return 'oevk.vportal-online.de';
            if (fed === 'BVDK_STAGING') return 'staging-bvdk.vportal-online.de';
            return 'bvdk.vportal-online.de';
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

        // Called when this device joins as display. Returns the session kind from
        // the server, or null if the lookup failed (the caller keeps its own).
        async startDisplayOverlay(sessionCode) {
            // Authoritative kind check — sessionKind in state may be stale after reload-recovery
            // because role-select didn't run on this page lifetime.
            let kind;
            try {
                const resp = await fetchFn(`/api/sessions/${sessionCode}`);
                if (!resp.ok) return null;
                const data = await resp.json();
                kind = data.kind || 'generic';
                this.stagingAvailable = !!data.staging_available;
            } catch (_e) {
                return null;
            }
            if (kind === 'vportal') this._startPolling(sessionCode);
            return kind;
        },

        _startPolling(sessionCode) {
            if (!client.isConnected(sessionCode)) return;
            const stored = client.getStored(sessionCode);
            if (!stored?.stage_id) return;
            this._pollStop = client.pollActiveAttempt(
                sessionCode,
                stored.fetch_interval_ms || 3000,
                (attempt) => {
                    if (attempt && attempt.__stale) {
                        return;
                    }
                    this.displayAttempt = attempt;
                    this.disconnectedReason = '';
                },
                (kind) => {
                    this.displayAttempt = null;
                    this.disconnectedReason = kind;
                },
            );
        },
    };
}
