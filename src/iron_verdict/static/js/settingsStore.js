// Session settings chosen by the head judge, registered as Alpine.store('settings').
// The server is authoritative: connection.js applies join_success and
// settings_update; the head judge's settings bar edits them and sends them back.

export function createSettingsStore() {
    return {
        liftType: 'squat',
        showExplanations: true,
        requireReasons: false,
        // The server refused the head judge's last lift type change because a judge
        // had already voted (#254); shown until the next lift or the next change sent.
        liftTypeLocked: false,
    };
}
