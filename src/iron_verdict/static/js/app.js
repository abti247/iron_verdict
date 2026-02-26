import { CARD_REASONS, ROLE_DISPLAY_NAMES } from './constants.js';
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
        displayStatus: 'Waiting for judges...',
        intentionalNavigation: false,
        showExplanations: false,
        requireReasons: false,
        selectedReason: null,
        showingReasonStep: false,
        liftType: 'squat',
        displayPhase: 'idle',
        displayShowExplanations: false,
        displayLiftType: 'squat',
        _phaseTimer1: null,
        judgeResultVotes: { left: null, center: null, right: null },
        judgeResultReasons: { left: null, center: null, right: null },
        contactName: '',
        contactEmail: '',
        contactMessage: '',
        contactStatus: 'idle',

        ...demoMethods,

        async createSession() {
            try {
                const response = await fetch('/api/sessions', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: this.newSessionName.trim() })
                });
                if (!response.ok) {
                    alert('Failed to create session. Please try again.');
                    return;
                }
                const data = await response.json();
                this.sessionCode = data.session_code;
                this.sessionName = this.newSessionName.trim();
                this.screen = 'role-select';
            } catch (error) {
                alert('Error creating session. Please check your connection.');
                console.error('Session creation error:', error);
            }
        },

        joinExistingSession() {
            if (this.joinCode) {
                this.sessionCode = this.joinCode.trim().toUpperCase();
                this.screen = 'role-select';
            }
        },

        joinSession(role) {
            this.role = role;
            const code = this.sessionCode || this.joinCode;
            this.sessionCode = code;
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
                    this.wsSend({ type: 'join', session_code: code, role: role });
                },
                () => { this.connectionStatus = 'reconnecting'; }
            );

            this.ws = wsWrapper;
            this.wsSend = (data) => wsWrapper.send(data);
        },

        handleMessage(message) {
            const dispatch = {
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
            };
            dispatch[message.type]?.(this, message);
        },

        selectVote(color) {
            if (!this.voteLocked) {
                this.selectedVote = color;
                this.selectedReason = null;
                this.showingReasonStep = (color !== 'white');
            }
        },

        goBackToColorStep() {
            this.showingReasonStep = false;
            this.selectedReason = null;
        },

        selectReason(reason) {
            this.selectedReason = reason;
        },

        getJudgeReasons() {
            const liftType = this.liftType || 'squat';
            return CARD_REASONS[liftType]?.[this.selectedVote] || [];
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
            localStorage.setItem('showExplanations', this.showExplanations);
            localStorage.setItem('liftType', this.liftType);
            localStorage.setItem('requireReasons', this.requireReasons);
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
            this.selectedVote = null;
            this.voteLocked = false;
            this.resultsShown = false;
            this.selectedReason = null;
            this.showingReasonStep = false;
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

        confirmEndSession() {
            if (confirm('Are you sure? This will disconnect all judges and the display')) {
                this.wsSend({ type: 'end_session_confirmed' });
            }
        },

        getRoleDisplayName() {
            return ROLE_DISPLAY_NAMES[this.role] || this.role;
        },

        isValidLift() {
            const whiteCount = Object.values(this.displayVotes).filter(c => c === 'white').length;
            return whiteCount >= 2;
        },

        returnToLanding() {
            this.intentionalNavigation = true;
            this.screen = 'landing';
            this.sessionCode = '';
            this.joinCode = '';
            this.isDemo = false;
            this.sessionName = '';
            this.newSessionName = '';
        },

        returnToRoleSelection() {
            this.intentionalNavigation = true;
            if (this.ws) {
                this.ws.close();
            }
            this.screen = 'role-select';
            this.selectedVote = null;
            this.voteLocked = false;
            this.resultsShown = false;
            this.selectedReason = null;
            this.showingReasonStep = false;
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
            this.screen = 'contact';
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
            this.showExplanations = localStorage.getItem('showExplanations') === 'true';
            this.liftType = localStorage.getItem('liftType') || 'squat';
            this.requireReasons = localStorage.getItem('requireReasons') === 'true';

            this.$watch('screen', (value) => {
                if (value === 'role-select' && this.sessionCode) {
                    setTimeout(() => this.generateQrCode(), 50);
                }
            });

            // QR code entry point: ?session=XXXX navigates to role-select
            const urlParams = new URLSearchParams(window.location.search);
            const urlSession = urlParams.get('session');
            if (urlSession) {
                history.replaceState({}, '', '/');
                this.sessionCode = urlSession.trim().toUpperCase();
                this.joinCode = this.sessionCode;
                this.screen = 'role-select';
                return;
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
        }
    };
}
