// "Connecting…" screen shown while a stored session is restored after a reload
// (reloadRecovery.js); its only action is to cancel and go to the landing screen.

export function reconnectingScreen(conn) {
    return {
        cancelReconnect() {
            conn.cancelReconnect();
        },
    };
}
