export function createWebSocket(url, onMessage, onError, onClose, onReopen, onDropped) {
    let ws;
    let stopped = false;
    let retryDelay = 1000;
    const MAX_DELAY = 16000;

    function connect() {
        ws = new WebSocket(url);

        ws.onmessage = (event) => onMessage(JSON.parse(event.data));
        ws.onerror = onError;
        ws.onclose = (event) => {
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
            ws.close();
        }
    };
}
