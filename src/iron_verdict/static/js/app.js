import { CARD_REASONS } from './constants.js';
import { startTimerCountdown } from './timer.js';
import { createWebSocket } from './websocket.js';
import { demoMethods } from './demo.js';
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
} from './handlers.js';

export function ironVerdictApp() {
    return {
        screen: 'landing',
        sessionCode: '',
        sessionName: '',
        newSessionName: '',
        isDemo: false,
        demoRunning: false,
        joinCode: '',
        joinError: '',
        joinChecking: false,
        role: '',
        isHead: false,
        ws: null,
        wsSend: null,
        connectionStatus: 'disconnected',
        serverRestarting: false,
        selectedVote: null,
        voteLocked: false,
        resultsShown: false,
        timerDisplay: '60',
        timerExpired: false,
        displayVotes: { left: null, center: null, right: null },
        displayReasons: { left: null, center: null, right: null },
        displayStatus: '',
        intentionalNavigation: false,
        showExplanations: false,
        requireReasons: false,
        selectedReason: null,
        showingReasonStep: false,
        reasonListOverflows: false,
        liftType: 'squat',
        displayPhase: 'idle',
        displayShowExplanations: false,
        displayLiftType: 'squat',
        _phaseTimer1: null,
        judgeResultVotes: { left: null, center: null, right: null },
        judgeResultReasons: { left: null, center: null, right: null },
        judgeConnected: { left: false, center: false, right: false },
        contactName: '',
        contactEmail: '',
        contactMessage: '',
        contactStatus: 'idle',

        ...demoMethods,

        navigateTo(screen) {
            if (this.screen === screen) return;
            this.screen = screen;
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
            try {
                const response = await fetch('/api/sessions', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: this.newSessionName.trim() })
                });
                if (!response.ok) {
                    alert(t('alerts.createFailed'));
                    return;
                }
                const data = await response.json();
                this.sessionCode = data.session_code;
                this.sessionName = this.newSessionName.trim();
                sessionStorage.setItem('iv_session', JSON.stringify({ code: this.sessionCode }));
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
            try {
                const res = await fetch('/api/sessions/' + code);
                if (res.ok) {
                    this.sessionCode = code;
                    this.joinCode = code;
                    sessionStorage.setItem('iv_session', JSON.stringify({ code }));
                    this.navigateTo('role-select');
                } else if (res.status === 404 || res.status === 422) {
                    sessionStorage.removeItem('iv_session');
                    this.joinError = t('landing.sessionNotFound');
                } else {
                    this.joinError = t('landing.lookupFailed');
                }
            } catch (_e) {
                this.joinError = t('landing.lookupFailed');
            } finally {
                this.joinChecking = false;
            }
        },

        joinSession(role) {
            this.role = role;
            const code = this.sessionCode || this.joinCode;
            this.sessionCode = code;
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
            this.connectionStatus = 'reconnecting';

            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const url = `${protocol}//${window.location.host}/ws`;

            const wsWrapper = createWebSocket(
                url,
                (message) => this.handleMessage(message),
                (error) => console.error('WebSocket error:', error),
                () => {},
                () => {
                    this.connectionStatus = 'connected';
                    this.serverRestarting = false;
                    let reconnectToken = null;
                    const stored = sessionStorage.getItem('iv_session');
                    if (stored) {
                        try { reconnectToken = JSON.parse(stored).reconnect_token || null; } catch (_e) {}
                    }
                    const joinMsg = { type: 'join', session_code: code, role: role };
                    if (reconnectToken) joinMsg.reconnect_token = reconnectToken;
                    this.wsSend(joinMsg);
                },
                () => { this.connectionStatus = 'reconnecting'; }
            );

            this.ws = wsWrapper;
            this.wsSend = (data) => wsWrapper.send(data);
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
            };
            dispatch[message.type]?.(this, message);
        },

        selectVote(color) {
            if (!this.voteLocked) {
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

        lockVote() {
            if (this.canLockIn()) {
                this.voteLocked = true;
                this.wsSend({
                    type: 'vote_lock',
                    color: this.selectedVote,
                    reason: this.selectedVote !== 'white' ? this.selectedReason : null,
                });
            }
        },

        saveSettings() {
            if (!this.isHead) return;
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
            this.voteLocked = false;
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
            if (this.role === 'center_judge') return t('roles.chiefReferee');
            const positionMap = { 'left_judge': 'left', 'right_judge': 'right' };
            const pos = positionMap[this.role];
            if (!pos) return this.role;
            return t('roles.' + pos);
        },

        isValidLift() {
            const whiteCount = Object.values(this.displayVotes).filter(c => c === 'white').length;
            return whiteCount >= 2;
        },

        returnToLanding() {
            sessionStorage.removeItem('iv_session');
            this.intentionalNavigation = true;
            if (this.ws) {
                this.ws.close();
            }
            this.navigateTo('landing');
            this.sessionCode = '';
            this.joinCode = '';
            this.isDemo = false;
            this.sessionName = '';
            this.newSessionName = '';
            this.joinError = '';
        },

        returnToRoleSelection() {
            // Downgrade to a code-only entry so a reload on role-select returns here.
            if (this.sessionCode) {
                sessionStorage.setItem('iv_session', JSON.stringify({ code: this.sessionCode }));
            } else {
                sessionStorage.removeItem('iv_session');
            }
            this.intentionalNavigation = true;
            if (this.ws) {
                this.ws.close();
            }
            this.navigateTo('role-select');
            this.selectedVote = null;
            this.voteLocked = false;
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
            if (!el || !this.sessionCode) return;
            while (el.firstChild) el.removeChild(el.firstChild);
            const url = window.location.origin + '/?session=' + this.sessionCode;
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
            // Capture URL params before scrubbing the query string via replaceState.
            const urlParams = new URLSearchParams(window.location.search);
            const urlSession = urlParams.get('session');
            history.replaceState({ screen: 'landing' }, '', '/');

            this.$watch('screen', (value) => {
                if (value === 'role-select' && this.sessionCode) {
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

            // Reload recovery: rejoin previous session or return to role-select.
            // Rehydration uses replaceState (via _navigateInPlaceNext) so the post-reload
            // back-stack matches the pre-reload one — mobile swipe-back stays consistent.
            const stored = sessionStorage.getItem('iv_session');
            if (stored) {
                try {
                    const { code, role } = JSON.parse(stored);
                    if (!code) {
                        sessionStorage.removeItem('iv_session');
                    } else if (role) {
                        this.sessionCode = code;
                        this.joinCode = code;
                        this._navigateInPlaceNext = true;
                        setTimeout(() => this.joinSession(role), 100);
                        return;
                    } else {
                        this.joinCode = code;
                        this._navigateInPlaceNext = true;
                        setTimeout(() => this.joinExistingSession(), 0);
                        return;
                    }
                } catch (_e) {
                    sessionStorage.removeItem('iv_session');
                }
            }

            const params = window._demoParams;
            if (params) {
                window._demoParams = null;
                this.sessionCode = params.code;
                this.joinCode = params.code;
                this.isDemo = true;
                setTimeout(() => this.joinSession(params.demo), 100);
            } else {
                this.screen = 'landing';
            }

            window.addEventListener('pageshow', (event) => {
                if (!event.persisted) return;
                const stored = sessionStorage.getItem('iv_session');
                if (!stored) return;
                try {
                    const { code, role } = JSON.parse(stored);
                    if (code && role && this.ws && this.ws.readyState === 3) {
                        this.joinSession(role);
                    }
                } catch (_e) {}
            });
        }
    };
}
