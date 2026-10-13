// Role taken over: a judge device rejoining with its reconnect token can get
// "Role already taken" because its token no longer matches. Either it is a short
// race (the server accepted this device on a connection that died before the new
// token arrived, and still counts that dead connection as connected) or another
// device has taken the position. The race ends once the server drops the dead
// connection, so after the give-up limit the device stops retrying and shows
// role-select with a notice instead of "Connecting…" forever.

// Why 25 s: the server closes a connection 15 s after its last pong and checks
// every 5 s (main.py), so the race is over after at most ~20 s; 5 s margin.
// This is a limit checked on each rejection, not a wait — retries continue as usual.
export const ROLE_TAKEN_GIVE_UP_MS = 25000;

const ROLE_LABEL_KEYS = {
    left_judge: 'roles.left',
    center_judge: 'roles.chiefReferee',
    right_judge: 'roles.right',
};

// Tracks one streak of "Role already taken" rejections. now: time source (ms).
export function createRoleTakenTracker(now = Date.now) {
    let since = null;
    return {
        // Call on each rejection; true once the streak has lasted the give-up limit.
        rejectedShouldGiveUp() {
            const t = now();
            if (since === null) since = t;
            return t - since >= ROLE_TAKEN_GIVE_UP_MS;
        },
        reset() {
            since = null;
        },
    };
}

export function roleTakenNotice(t, role) {
    const label = t(ROLE_LABEL_KEYS[role]).replace(/\s*\n\s*/g, ' ');
    return t('roleTakenOver.notice').replace('{role}', label);
}

export const roleTakeoverMethods = {
    // Give up rejoining: role-select of the same session (drops the reconnect token
    // and closes the socket) with a notice naming the position.
    failRoleTakenOver() {
        const notice = roleTakenNotice(t, this.role);
        this.returnToRoleSelection();
        this.roleNotice = notice;
    },
};
