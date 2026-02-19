# Deployment Guide

## Production Deployment with TLS

Use [Caddy](https://caddyserver.com/) as a reverse proxy. It provisions and renews Let's Encrypt certificates automatically.

### 1. Install Caddy

Follow the [official installation guide](https://caddyserver.com/docs/install) for your OS.

### 2. Create a Caddyfile

```
yourdomain.com {
    reverse_proxy localhost:8000
}
```

Caddy handles HTTPS automatically. Port 80 and 443 must be open.

### 3. Run JudgeMe

```bash
uvicorn judgeme.main:app --host 127.0.0.1 --port 8000
```

Bind to `127.0.0.1` so the app is only reachable through Caddy, not directly from the internet.

### 4. Environment Variables

| Variable | Default | Description |
|---|---|---|
| `ALLOWED_ORIGIN` | `*` | Restrict WebSocket origin. Set to `https://yourdomain.com` in production. |
| `SESSION_TIMEOUT_HOURS` | `24` | Hours before idle sessions are cleaned up. |
| `DISPLAY_CAP` | `20` | Max simultaneous display connections per session. |
| `ENV` | _(unset)_ | Set to `development` to enable Uvicorn auto-reload. |

### Security Notes

- Set `ALLOWED_ORIGIN=https://yourdomain.com` — prevents WebSocket connections from foreign origins.
- Bind Uvicorn to `127.0.0.1`, not `0.0.0.0` — keeps the app behind Caddy.
- The app sends `Strict-Transport-Security` headers; browsers enforce HTTPS after first visit.
- CSP currently allowlists `cdn.jsdelivr.net` for Alpine.js. To tighten: self-host Alpine.js and change `script-src` to `'self'` only.
