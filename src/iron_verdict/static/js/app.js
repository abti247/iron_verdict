import { CARD_REASONS } from './constants.js';
import { startTimerCountdown } from './timer.js';
import { createWebSocket } from './websocket.js';
import { demoMethods } from './demo.js';
import { voteDeliveryMethods } from './voteDelivery.js';
import { reloadRecoveryMethods } from './reloadRecovery.js';
import { roleTakeoverMethods, createRoleTakenTracker } from './roleTakeover.js';
import {
    handleJoinSuccess,
    handleJoinError,
    handleError,
    handleShowResults,
    handleResetForNextLift,
    handleTimerStart,
    handleTimerReset,
    handleSessionEnded,
    handleSettingsUpdate,
    handleServerRestarting,
    handleJudgeStatusUpdate,
    handleVoteAck,
    handleVoteRejected,
} from './handlers.js';

const DISPLAY_ZOOM_KEY = 'iron-verdict:display-zoom';

export function ironVerdictApp() {
    return {
        screen: 'landing',
        newSessionName: '',
        isDemo: false,
        demoRunning: false,
        joinCode: '',
        joinError: '',
        joinChecking: false,
        roleTakenOver: '',  // role whose position another device took; shows the role-select notice
        _roleTaken: createRoleTakenTracker(),  // "Role already taken" streak, see roleTakeover.js
        ws: null,
        wsSend: null,
        selectedVote: null,
        voteState: 'open',  // 'open' | 'sending' | 'confirmed' — see voteDelivery.js
        voteError: '',      // i18n key of the last vote rejection, '' if none
        liftId: null,
        get voteLocked() { return this.voteState !== 'open'; },
        resultsShown: false,
        timerDisplay: '60',
        timerExpired: false,
        displayVotes: { left: null, center: null, right: null },
        displayReasons: { left: null, center: null, right: null },
        displayStatus: '',
        intentionalNavigation: false,
        showExplanations: true,
        requireReasons: false,
        selectedReason: null,
        showingReasonStep: false,
        reasonListOverflows: false,
        liftType: 'squat',
        displayPhase: 'idle',
        displayShowExplanations: true,
        displayLiftType: 'squat',
        _phaseTimer1: null,
        judgeResultVotes: { left: null, center: null, right: null },
        judgeResultReasons: { left: null, center: null, right: null },
        contactName: '',
        contactEmail: '',
        contactMessage: '',
        contactStatus: 'idle',

        displaySettingsOpen: false,
        displayZoom: 1,
        _displayKeydownHandler: null,

        ...demoMethods,
        ...voteDeliveryMethods,
        ...reloadRecoveryMethods,
        ...roleTakeoverMethods,

        navigateTo(screen) {
            if (this.screen === screen) return;
            this.screen = screen;
            this.displaySettingsOpen = false;
            if (this._handlingPopstate) return;
            if (this._navigateInPlaceNext) {
                // One-shot: rehydrating state in init() — keep the back-stack the same depth
                // as it was before the reload so mobile swipe-back keeps working.
                this._navigateInPlaceNext = false;
                history.replaceState({ screen }, '', '/');
            } else {
                history.pushState({ screen }, '', '/');
            }
        },

        async createSession() {
            const session = this.$store.session;
            try {
                session.kind = this._initialPathname === '/vportal' ? 'vportal' : 'generic';
                const response = await fetch('/api/sessions', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        name: this.newSessionName.trim(),
                        kind: session.kind,
                    })
                });
                if (!response.ok) {
                    alert(t('alerts.createFailed'));
                    return;
                }
                const data = await response.json();
                session.code = data.session_code;
                session.name = this.newSessionName.trim();
                await this.$store.vportal.loadStagingFlag(session.code);
                sessionStorage.setItem('iv_session', JSON.stringify({ code: session.code }));
                this.navigateTo('role-select');
            } catch (error) {
                alert(t('alerts.createError'));
                console.error('Session creation error:', error);
            }
        },

        async joinExistingSession() {
            const code = this.joinCode.trim().toUpperCase();
            if (code.length !== 8 || this.joinChecking) return;
            this.joinChecking = true;
            this.joinError = '';
            const restoring = this.screen === 'reconnecting';
            try {
                const res = await fetch('/api/sessions/' + code);
                // Reload recovery cancelled while the lookup was running — the user left on purpose.
                if (this.isReconnectCancelled(restoring)) return;
                if (res.ok) {
                    this.$store.session.code = code;
                    this.joinCode = code;
                    try {
                        const data = await res.json();
                        this.$store.session.kind = data.kind || 'generic';
                        this.$store.vportal.applySessionInfo(data);
                    } catch (_e) {
                        this.$store.session.kind = 'generic';
                        this.$store.vportal.applySessionInfo(null);
                    }
                    sessionStorage.setItem('iv_session', JSON.stringify({ code }));
                    this.navigateTo('role-select');
                } else if (res.status === 404 || res.status === 422) {
                    if (this.screen === 'reconnecting') {
                        this.failReconnectSessionGone();
                        return;
                    }
                    sessionStorage.removeItem('iv_session');
                    this.joinError = t('landing.sessionNotFound');
                } else {
                    this.navigateTo('landing');
                    this.joinError = t('landing.lookupFailed');
                }
            } catch (_e) {
                if (this.isReconnectCancelled(restoring)) return;
                this.navigateTo('landing');
                this.joinError = t('landing.lookupFailed');
            } finally {
                this.joinChecking = false;
            }
        },

        joinSession(role) {
            const session = this.$store.session;
            session.role = role;
            this.roleTakenOver = '';
            this._roleTaken.reset();
            const code = session.code || this.joinCode;
            session.code = code;
            const sessionEntry = { code, role };
            const existingSession = sessionStorage.getItem('iv_session');
            if (existingSession) {
                try {
                    const parsed = JSON.parse(existingSession);
                    if (parsed.code === code && parsed.role === role && parsed.reconnect_token) {
                        sessionEntry.reconnect_token = parsed.reconnect_token;
                    }
                } catch (_e) {}
            }
            sessionStorage.setItem('iv_session', JSON.stringify(sessionEntry));
            session.connectionStatus = 'reconnecting';

            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const url = `${protocol}//${window.location.host}/ws`;

            const wsWrapper = createWebSocket(
                url,
                (message) => this.handleMessage(message),
                (error) => console.error('WebSocket error:', error),
                () => {},
                () => {
                    session.connectionStatus = 'connected';
                    session.serverRestarting = false;
                    let reconnectToken = null;
                    const stored = sessionStorage.getItem('iv_session');
                    if (stored) {
                        try { reconnectToken = JSON.parse(stored).reconnect_token || null; } catch (_e) {}
                    }
                    const joinMsg = { type: 'join', session_code: code, role: role };
                    if (reconnectToken) joinMsg.reconnect_token = reconnectToken;
                    this.wsSend(joinMsg);
                },
                () => { session.connectionStatus = 'reconnecting'; }
            );

            this.ws = wsWrapper;
            this.wsSend = (data) => wsWrapper.send(data);
            if (role === 'display') {
                this.$store.vportal.startDisplayOverlay(code).then((kind) => {
                    if (kind) session.kind = kind;
                }).catch((err) => console.warn('VPortal display overlay failed to start', err));
            }
        },

        handleMessage(message) {
            const dispatch = {
                ping:                (self) => self.wsSend({ type: "pong" }),
                join_success:        handleJoinSuccess,
                join_error:          handleJoinError,
                error:               handleError,
                show_results:        handleShowResults,
                reset_for_next_lift: handleResetForNextLift,
                timer_start:         handleTimerStart,
                timer_reset:         handleTimerReset,
                session_ended:       handleSessionEnded,
                settings_update:     handleSettingsUpdate,
                server_restarting:   handleServerRestarting,
                judge_status_update: handleJudgeStatusUpdate,
                vote_ack:            handleVoteAck,
                vote_rejected:       handleVoteRejected,
            };
            dispatch[message.type]?.(this, message);
        },

        selectVote(color) {
            if (!this.voteLocked) {
                this.voteError = '';
                this.selectedVote = color;
                this.selectedReason = null;
                this.showingReasonStep = (color !== 'white');
                if (color !== 'white') {
                    this.$nextTick(() => this.initReasonScrollIndicator());
                }
            }
        },

        goBackToColorStep() {
            this.cleanupReasonScroll();
            this.showingReasonStep = false;
            this.selectedReason = null;
            this.reasonListOverflows = false;
        },

        initReasonScrollIndicator() {
            const list = this.$refs.reasonList;
            if (!list) return;
            this.cleanupReasonScroll();

            const check = () => {
                this.reasonListOverflows = list.scrollHeight > list.clientHeight
                    && list.scrollTop + list.clientHeight < list.scrollHeight - 4;
            };
            check();

            this._reasonScrollHandler = () => check();
            list.addEventListener('scroll', this._reasonScrollHandler, { passive: true });

            this._reasonResizeHandler = () => {
                clearTimeout(this._resizeTimer);
                this._resizeTimer = setTimeout(check, 200);
            };
            window.addEventListener('resize', this._reasonResizeHandler);
        },

        cleanupReasonScroll() {
            const list = this.$refs.reasonList;
            if (this._reasonScrollHandler && list) {
                list.removeEventListener('scroll', this._reasonScrollHandler);
            }
            if (this._reasonResizeHandler) {
                window.removeEventListener('resize', this._reasonResizeHandler);
            }
            clearTimeout(this._resizeTimer);
            this._reasonScrollHandler = null;
            this._reasonResizeHandler = null;
            this._resizeTimer = null;
        },

        selectReason(reason) {
            this.selectedReason = reason;
        },

        getJudgeReasons() {
            const liftType = this.liftType || 'squat';
            const reasonIds = CARD_REASONS[liftType]?.[this.selectedVote] || [];
            return reasonIds.map(id => ({ id, label: t(id) }));
        },

        canLockIn() {
            if (!this.selectedVote || this.voteLocked) return false;
            if (this.selectedVote === 'white') return true;
            if (this.requireReasons) return !!this.selectedReason;
            return true;
        },

        saveSettings() {
            if (!this.$store.session.isHead) return;
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.wsSend({
                    type: 'settings_update',
                    showExplanations: this.showExplanations,
                    liftType: this.liftType,
                    requireReasons: this.requireReasons
                });
            }
        },

        resetVoting() {
            this.cleanupReasonScroll();
            this.selectedVote = null;
            this.voteState = 'open';
            this.voteError = '';
            this.clearPendingVote();
            this.resultsShown = false;
            this.selectedReason = null;
            this.showingReasonStep = false;
            this.reasonListOverflows = false;
            this.judgeResultVotes = { left: null, center: null, right: null };
            this.judgeResultReasons = { left: null, center: null, right: null };
        },

        startTimer() {
            this.wsSend({ type: 'timer_start' });
        },

        resetTimer() {
            this.wsSend({ type: 'timer_reset' });
        },

        startTimerCountdown(timeRemainingMs) {
            startTimerCountdown(timeRemainingMs, (seconds, expired) => {
                this.timerDisplay = seconds;
                this.timerExpired = expired;
            });
        },

        nextLift() {
            this.wsSend({ type: 'next_lift' });
        },

        nextLiftGuarded() {
            if (this.resultsShown || confirm(t('alerts.confirmAdvance'))) {
                this.nextLift();
            }
        },

        confirmEndSession() {
            if (confirm(t('alerts.confirmEnd'))) {
                this.wsSend({ type: 'end_session_confirmed' });
            }
        },

        getRoleDisplayName() {
            const session = this.$store.session;
            if (session.role === 'center_judge') return t('roles.chiefReferee');
            const positionMap = { 'left_judge': 'left', 'right_judge': 'right' };
            const pos = positionMap[session.role];
            if (!pos) return session.role;
            return t('roles.' + pos);
        },

        isValidLift() {
            const whiteCount = Object.values(this.displayVotes).filter(c => c === 'white').length;
            return whiteCount >= 2;
        },

        returnToLanding() {
            sessionStorage.removeItem('iv_session');
            this.$store.vportal.stopDisplayOverlay();
            this.clearPendingVote();
            this.intentionalNavigation = true;
            if (this.ws) {
                this.ws.close();
            }
            this.navigateTo('landing');
            this.$store.session.code = '';
            this.joinCode = '';
            this.isDemo = false;
            this.$store.session.name = '';
            this.newSessionName = '';
            this.joinError = '';
            this.roleTakenOver = '';
        },

        returnToRoleSelection() {
            this.$store.vportal.stopDisplayOverlay();
            // Downgrade to a code-only entry so a reload on role-select returns here.
            if (this.$store.session.code) {
                sessionStorage.setItem('iv_session', JSON.stringify({ code: this.$store.session.code }));
            } else {
                sessionStorage.removeItem('iv_session');
            }
            this.intentionalNavigation = true;
            if (this.ws) {
                this.ws.close();
            }
            this.navigateTo('role-select');
            this.clearPendingVote();
            this.selectedVote = null;
            this.voteState = 'open';
            this.voteError = '';
            this.resultsShown = false;
            this.selectedReason = null;
            this.cleanupReasonScroll();
            this.showingReasonStep = false;
            this.reasonListOverflows = false;
            startTimerCountdown(0, () => {});
            this.timerDisplay = '60';
            this.timerExpired = false;
        },

        generateQrCode() {
            const el = document.getElementById('qrcode');
            if (!el || !this.$store.session.code) return;
            while (el.firstChild) el.removeChild(el.firstChild);
            const url = window.location.origin + '/?session=' + this.$store.session.code;
            new QRCode(el, {
                text: url,
                width: 200,
                height: 200,
                colorDark: '#000000',
                colorLight: '#ffffff',
            });
        },

        goToContact() {
            this.contactName = '';
            this.contactEmail = '';
            this.contactMessage = '';
            this.contactStatus = 'idle';
            this.navigateTo('contact');
        },

        openDisplaySettings() {
            this.displaySettingsOpen = true;
        },

        closeDisplaySettings() {
            this.displaySettingsOpen = false;
        },

        resetDisplayZoom() {
            this.displayZoom = 1;
            try { localStorage.setItem(DISPLAY_ZOOM_KEY, '1'); } catch (_) {}
        },

        onDisplayZoomInput(event) {
            const n = parseFloat(event.target.value);
            if (!Number.isFinite(n)) return;
            this.displayZoom = Math.min(1.5, Math.max(0.7, n));
            try { localStorage.setItem(DISPLAY_ZOOM_KEY, String(this.displayZoom)); } catch (_) {}
        },

        _loadDisplayZoomFromStorage() {
            try {
                const raw = localStorage.getItem(DISPLAY_ZOOM_KEY);
                if (raw == null) return;
                const n = parseFloat(raw);
                if (!Number.isFinite(n)) return;
                this.displayZoom = Math.min(1.5, Math.max(0.7, n));
            } catch (_) {}
        },

        _installDisplayKeyHandler() {
            if (this._displayKeydownHandler) return;
            this._displayKeydownHandler = (e) => {
                if (this.screen !== 'display') return;
                const tag = (e.target && e.target.tagName) || '';
                if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
                if (e.key === 's' || e.key === 'S') {
                    e.preventDefault();
                    this.displaySettingsOpen = !this.displaySettingsOpen;
                } else if (e.key === 'Escape' && this.displaySettingsOpen) {
                    e.preventDefault();
                    this.displaySettingsOpen = false;
                }
            };
            window.addEventListener('keydown', this._displayKeydownHandler);
        },

        async submitContact() {
            this.contactStatus = 'loading';
            try {
                const res = await fetch('https://api.web3forms.com/submit', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
                    body: JSON.stringify({
                        access_key: '2e92ea27-be19-4996-83c9-0b33fcb63419',
                        name: this.contactName,
                        email: this.contactEmail,
                        message: this.contactMessage,
                    })
                });
                const data = await res.json();
                this.contactStatus = data.success ? 'success' : 'error';
            } catch (_e) {
                this.contactStatus = 'error';
            }
        },

        init() {
            // Capture URL params and pathname before scrubbing via replaceState.
            const urlParams = new URLSearchParams(window.location.search);
            const urlSession = urlParams.get('session');
            this._initialPathname = window.location.pathname;
            history.replaceState({ screen: 'landing' }, '', '/');

            this._loadDisplayZoomFromStorage();
            this._installDisplayKeyHandler();

            this.$watch('screen', (value) => {
                if (value === 'role-select' && this.$store.session.code) {
                    setTimeout(() => this.generateQrCode(), 50);
                }
            });

            // QR code entry point: ?session=XXXX validates code, then navigates to role-select
            if (urlSession) {
                const trimmed = urlSession.trim().toUpperCase();
                this.joinCode = trimmed;
                this.screen = 'landing';
                if (trimmed.length === 8) {
                    // Defer until Alpine has wired the rest of init
                    setTimeout(() => this.joinExistingSession(), 0);
                } else if (trimmed.length > 0) {
                    this.joinError = t('landing.sessionNotFound');
                }
                return;
            }

            // Reload recovery: rejoin the previous session or return to role-select (reloadRecovery.js).
            if (this.restoreStoredSession()) return;

            const params = window._demoParams;
            if (params) {
                window._demoParams = null;
                this.$store.session.code = params.code;
                this.joinCode = params.code;
                this.isDemo = true;
                setTimeout(() => this.joinSession(params.demo), 100);
            } else {
                this.screen = 'landing';
            }
        }
    };
}
