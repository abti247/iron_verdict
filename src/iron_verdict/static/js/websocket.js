// Heartbeat watchdog. The server pings every 5 s (main.py HEARTBEAT_INTERVAL_SECONDS);
// a half-open connection (e.g. device switched Wi-Fi access point) often never fires
// onclose, so the client treats 15 s without any server message (3 missed pings) as
// dead and reconnects. The check interval only bounds detection latency (15–17.5 s).
export const WATCHDOG_STALE_MS = 15000;
export const WATCHDOG_CHECK_MS = 2500;
// A gap this large between two checks means the browser paused or throttled timers
// (background tab, frozen page); incoming messages may still be queued behind it,
// so the watchdog restarts its count instead of declaring the connection dead.
const WATCHDOG_PAUSE_MS = WATCHDOG_CHECK_MS * 2;

export function createWebSocket(url, onMessage, onError, onClose, onReopen, onDropped) {
    let ws;
    let stopped = false;
    let retryDelay = 1000;
    const MAX_DELAY = 16000;
    let watchdog = null;
    let lastActivity = 0;
    let lastCheck = 0;

    function stopWatchdog() {
        clearInterval(watchdog);
        watchdog = null;
    }

    function startWatchdog() {
        stopWatchdog();
        lastActivity = lastCheck = Date.now();
        watchdog = setInterval(() => {
            const now = Date.now();
            if (now - lastCheck > WATCHDOG_PAUSE_MS) lastActivity = now;
            lastCheck = now;
            if (now - lastActivity > WATCHDOG_STALE_MS) forceReconnect();
        }, WATCHDOG_CHECK_MS);
    }

    // Abandon the current socket and connect a new one right away. Unlike close(),
    // this keeps the wrapper alive. The old socket's handlers are detached first:
    // on a half-open connection its onclose may only fire much later, and must not
    // trigger a second reconnect or deliver stale messages.
    function forceReconnect() {
        if (stopped) return;
        stopWatchdog();
        const old = ws;
        old.onmessage = old.onerror = old.onclose = old.onopen = null;
        try { old.close(); } catch (_e) {}
        console.log('WebSocket heartbeat lost, reconnecting now...');
        onDropped?.();
        connect();
    }

    function connect() {
        ws = new WebSocket(url);

        ws.onmessage = (event) => {
            lastActivity = Date.now();
            onMessage(JSON.parse(event.data));
        };
        ws.onerror = onError;
        ws.onclose = (event) => {
            stopWatchdog();
            if (stopped) {
                onClose(event);
                return;
            }
            onDropped?.();
            console.log(`WebSocket closed, reconnecting in ${retryDelay}ms...`);
            setTimeout(() => {
                if (!stopped) {
                    retryDelay = Math.min(retryDelay * 2, MAX_DELAY);
                    connect();
                }
            }, retryDelay);
        };
        ws.onopen = () => {
            retryDelay = 1000;
            startWatchdog();
            onReopen?.();
        };
    }

    connect();

    return {
        get readyState() { return ws.readyState; },
        send: (data) => {
            if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(data));
        },
        close: () => {
            stopped = true;
            stopWatchdog();
            ws.close();
        }
    };
}
