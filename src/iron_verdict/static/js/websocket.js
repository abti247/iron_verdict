export function createWebSocket(url, onMessage, onError, onClose) {
    const ws = new WebSocket(url);

    ws.onmessage = (event) => onMessage(JSON.parse(event.data));
    ws.onerror = onError;
    ws.onclose = onClose;

    return {
        ws,
        send: (data) => ws.send(JSON.stringify(data))
    };
}
