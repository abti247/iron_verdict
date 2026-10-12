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

// Wait between reconnect attempts, by attempt number (the last value repeats).
// Short on purpose: a session has ~5 clients, so a reconnect storm is no risk,
// while every second offline is a vote or result that does not arrive.
// The jitter keeps clients from hitting a restarted server in the same instant.
export const RETRY_DELAYS_MS = [500, 1000, 2000, 3000];
export const RETRY_JITTER = 0.2;

export function retryDelay(attempt, random = Math.random) {
    const base = RETRY_DELAYS_MS[Math.min(attempt, RETRY_DELAYS_MS.length - 1)];
    return Math.round(base * (1 + RETRY_JITTER * (2 * random() - 1)));
}

export function createWebSocket(url, onMessage, onError, onClose, onReopen, onDropped) {
    let ws;
    let stopped = false;
    let attempt = 0;
    let retryTimer = null;
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
            if (now - lastActivity > WATCHDOG_STALE_MS) forceReconnect('heartbeat lost');
        }, WATCHDOG_CHECK_MS);
    }

    // Abandon the current socket and connect a new one right away. Unlike close(),
    // this keeps the wrapper alive. The old socket's handlers are detached first:
    // on a half-open connection its onclose may only fire much later, and must not
    // trigger a second reconnect or deliver stale messages.
    function forceReconnect(reason) {
        if (stopped) return;
        stopWatchdog();
        const old = ws;
        old.onmessage = old.onerror = old.onclose = old.onopen = null;
        try { old.close(); } catch (e) { console.warn('Closing abandoned WebSocket failed:', e); }
        console.log(`WebSocket ${reason}, reconnecting now...`);
        onDropped?.();
        connect();
    }

    // The device is back online, the tab is visible again or the page came back
    // from the back/forward cache: skip the rest of a pending retry wait. An open
    // socket or a connection attempt in progress is left alone (the watchdog
    // covers an open-but-dead socket), so this never creates a second socket.
    function reconnectNow() {
        if (stopped) return;
        if (retryTimer !== null) {
            clearTimeout(retryTimer);
            retryTimer = null;
            connect();
        } else if (ws.readyState === WebSocket.CLOSED) {
            // Closed while the page was frozen, without a close event reaching us.
            forceReconnect('closed while the page was frozen');
        }
    }

    const onOnline = () => reconnectNow();
    const onVisibilityChange = () => {
        if (document.visibilityState === 'visible') reconnectNow();
    };
    const onPageShow = (event) => {
        if (event.persisted) reconnectNow();
    };

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
            const delay = retryDelay(attempt++);
            console.log(`WebSocket closed, reconnecting in ${delay}ms...`);
            retryTimer = setTimeout(() => {
                retryTimer = null;
                if (!stopped) connect();
            }, delay);
        };
        ws.onopen = () => {
            attempt = 0;
            startWatchdog();
            onReopen?.();
        };
    }

    window.addEventListener('online', onOnline);
    window.addEventListener('pageshow', onPageShow);
    document.addEventListener('visibilitychange', onVisibilityChange);
    connect();

    return {
        get readyState() { return ws.readyState; },
        send: (data) => {
            if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(data));
        },
        close: () => {
            stopped = true;
            stopWatchdog();
            clearTimeout(retryTimer);
            retryTimer = null;
            window.removeEventListener('online', onOnline);
            window.removeEventListener('pageshow', onPageShow);
            document.removeEventListener('visibilitychange', onVisibilityChange);
            ws.close();
        }
    };
}
