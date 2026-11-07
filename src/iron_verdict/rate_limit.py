"""Per-client-IP rate limiting (slowapi), shared by the app and the VPortal proxy.

Why its own module: `main` includes the VPortal router, so the proxy cannot
import the limiter from `main` without a circular import.
"""

from fastapi import Request, WebSocket
from slowapi import Limiter


def client_ip(headers, client) -> str:
    # Production runs behind Cloudflare and Railway's edge proxy: the TCP peer
    # is a Railway 100.64.0.0/10 address that changes even for one client.
    # Cloudflare sets CF-Connecting-IP to the real client and overwrites any
    # value the client sends. X-Forwarded-For is not used: its first entry is
    # whatever the client put there.
    cf_ip = headers.get("cf-connecting-ip", "").strip()
    if cf_ip:
        return cf_ip
    return client.host if client else "unknown"


def get_http_client_ip(request: Request) -> str:
    return client_ip(request.headers, request.client)


def get_ws_client_ip(websocket: WebSocket) -> str:
    return client_ip(websocket.headers, websocket.client)


limiter = Limiter(key_func=get_http_client_ip)
