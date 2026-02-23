import { CARD_REASONS, ROLE_DISPLAY_NAMES } from './constants.js';
import { startTimerCountdown, stopTimer } from './timer.js';
import { createWebSocket } from './websocket.js';

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
                this.sessionCode = this.joinCode;
                this.screen = 'role-select';
            }
        },

        joinSession(role) {
            this.role = role;
            const code = this.sessionCode || this.joinCode;
            this.sessionCode = code;

            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const url = `${protocol}//${window.location.host}/ws`;

            const { ws, send } = createWebSocket(
                url,
                (message) => this.handleMessage(message),
                (error) => {
                    console.error('WebSocket error:', error);
                    alert('Connection error. Please check your network and try again.');
                },
                (event) => {
                    if (!event.wasClean && !this.intentionalNavigation) {
                        console.error('WebSocket closed unexpectedly:', event);
                        alert('Connection lost. Please refresh and try again.');
                    }
                }
            );

            this.ws = ws;
            this.wsSend = send;

            ws.onopen = () => {
                send({ type: 'join', session_code: code, role: role });
            };
        },

        handleMessage(message) {
            if (message.type === 'join_success') {
                this.isHead = message.is_head;
                this.sessionName = message.session_state?.name || '';
                this.screen = this.role === 'display' ? 'display' : 'judge';
                if (this.isHead) {
                    this.requireReasons = message.session_state?.settings?.require_reasons ?? false;
                    this.saveSettings();  // sync localStorage settings to server
                }
                const trms = message.session_state?.time_remaining_ms;
                if (trms > 0) {
                    this.startTimerCountdown(trms);
                }
            } else if (message.type === 'join_error') {
                const sanitizedMessage = document.createTextNode(message.message).textContent;
                alert(`Failed to join session: ${sanitizedMessage}`);
            } else if (message.type === 'error') {
                const sanitizedMessage = document.createTextNode(message.message).textContent;
                alert(`Error: ${sanitizedMessage}`);
            } else if (message.type === 'show_results') {
                this.resultsShown = true;
                stopTimer();
                this.judgeResultVotes = message.votes;
                this.judgeResultReasons = message.reasons || { left: null, center: null, right: null };
                if (this.role === 'display') {
                    clearTimeout(this._phaseTimer1);
                    this.displayVotes = this.judgeResultVotes;
                    this.displayReasons = this.judgeResultReasons;
                    this.displayShowExplanations = message.showExplanations;
                    this.displayLiftType = message.liftType;
                    this.displayPhase = 'votes';
                    this.displayStatus = '';
                }
            } else if (message.type === 'reset_for_next_lift') {
                clearTimeout(this._phaseTimer1);
                this.resetVoting();
                stopTimer();
                this.timerDisplay = '60';
                this.timerExpired = false;
                if (this.role === 'display') {
                    this.displayVotes = { left: null, center: null, right: null };
                    this.displayReasons = { left: null, center: null, right: null };
                    this.displayPhase = 'idle';
                    this.displayStatus = 'Waiting for judges...';
                }
            } else if (message.type === 'timer_start') {
                this.startTimerCountdown(message.time_remaining_ms);
            } else if (message.type === 'timer_reset') {
                stopTimer();
                this.timerDisplay = '60';
                this.timerExpired = false;
            } else if (message.type === 'session_ended') {
                alert('Session ended');
                this.ws.close();
                this.isDemo = false;
                this.screen = 'landing';
            } else if (message.type === 'settings_update') {
                if (message.showExplanations !== undefined) {
                    this.showExplanations = message.showExplanations;
                }
                if (message.liftType !== undefined) {
                    this.liftType = message.liftType;
                }
                if (message.requireReasons !== undefined) {
                    this.requireReasons = message.requireReasons;
                }
            }
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
            stopTimer();
            this.timerDisplay = '60';
            this.timerExpired = false;
        },

        getWindowSpecs(sessionCode) {
            const sw = window.screen.width;
            const sh = window.screen.height;
            const jw = Math.floor(sw / 3);
            const jh = Math.floor(sh / 2);
            const dw = sw;
            const dh = Math.floor(sh / 2);
            const sl = window.screen.availLeft ?? 0;
            const st = window.screen.availTop ?? 0;

            const baseUrl = `${window.location.origin}/?code=${sessionCode}`;

            return {
                leftJudge:   { url: `${baseUrl}&demo=left_judge`,   params: `width=${jw},height=${jh},left=${sl},top=${st}` },
                centerJudge: { url: `${baseUrl}&demo=center_judge`, params: `width=${jw},height=${jh},left=${sl+jw},top=${st}` },
                rightJudge:  { url: `${baseUrl}&demo=right_judge`,  params: `width=${jw},height=${jh},left=${sl+2*jw},top=${st}` },
                display:     { url: `${baseUrl}&demo=display`,      params: `width=${dw},height=${dh},left=${sl},top=${st+jh}` }
            };
        },

        startDemo() {
            this.demoRunning = false;
            this.screen = 'demo-intro';
        },

        async launchDemo() {
            try {
                const response = await fetch('/api/sessions', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: 'Demo' })
                });
                if (!response.ok) {
                    alert('Failed to create session. Please try again.');
                    return;
                }
                const data = await response.json();
                const sessionCode = data.session_code;

                const specs = this.getWindowSpecs(sessionCode);
                const timestamp = Date.now();
                window.open(specs.leftJudge.url,   `leftJudge_${timestamp}`,   specs.leftJudge.params);
                window.open(specs.centerJudge.url, `centerJudge_${timestamp}`, specs.centerJudge.params);
                window.open(specs.rightJudge.url,  `rightJudge_${timestamp}`,  specs.rightJudge.params);
                window.open(specs.display.url,     `display_${timestamp}`,     specs.display.params);

                this.demoRunning = true;
            } catch (error) {
                alert('Failed to start demo. Please try again.');
                console.error('Demo mode error:', error);
            }
        },

        returnToLandingFromDemo() {
            this.demoRunning = false;
            this.screen = 'landing';
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
