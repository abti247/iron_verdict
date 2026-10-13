// Judge screen: vote buttons and reason step, vote status, the lift's result and,
// for the head judge, timer/lift/session controls and the settings bar. Vote and
// result state live in Alpine.store('judge'); this component only holds the
// reason-list scroll hint.

import { CARD_REASONS } from '../constants.js';

export function judgeScreen(conn) {
    return {
        reasonListOverflows: false,
        _reasonScrollHandler: null,
        _reasonResizeHandler: null,
        _resizeTimer: null,

        init() {
            // The reason step opens on a red/blue/yellow choice and closes on Back,
            // a reset or a rejection — whoever changed the store.
            this.$watch('$store.judge.showingReasonStep', (showing) => {
                if (showing) {
                    this.$nextTick(() => this.initReasonScrollIndicator());
                } else {
                    this.cleanupReasonScroll();
                    this.reasonListOverflows = false;
                }
            });
        },

        getRoleDisplayName() {
            const session = this.$store.session;
            if (session.role === 'center_judge') return t('roles.chiefReferee');
            const positionMap = { 'left_judge': 'left', 'right_judge': 'right' };
            const pos = positionMap[session.role];
            if (!pos) return session.role;
            return t('roles.' + pos);
        },

        getJudgeReasons() {
            const liftType = this.$store.settings.liftType || 'squat';
            const reasonIds = CARD_REASONS[liftType]?.[this.$store.judge.selectedVote] || [];
            return reasonIds.map(id => ({ id, label: t(id) }));
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

        saveSettings() {
            conn.sendSettings();
        },

        startTimer() {
            conn.send({ type: 'timer_start' });
        },

        resetTimer() {
            conn.send({ type: 'timer_reset' });
        },

        nextLiftGuarded() {
            if (this.$store.judge.resultsShown || confirm(t('alerts.confirmAdvance'))) {
                conn.send({ type: 'next_lift' });
            }
        },

        confirmEndSession() {
            if (confirm(t('alerts.confirmEnd'))) {
                conn.send({ type: 'end_session_confirmed' });
            }
        },

        returnToRoleSelection() {
            conn.returnToRoleSelection();
        },
    };
}
