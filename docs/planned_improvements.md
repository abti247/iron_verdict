# Planned Improvements

## Auto-reconnect after server restart

**Context:** When the server restarts (deploy, crash), judges see a browser alert — "Connection lost. Please refresh and try again." — and must manually re-enter their session code and role.

**Improvement:** Make reconnection seamless.

**How:**
1. Handle `server_restarting` message in app.js — show a "Reconnecting..." UI state instead of an alert.
2. Save session code + role in `sessionStorage` on successful join.
3. On WebSocket close, auto-retry the connection every N seconds.
4. On reconnect, read session code + role from `sessionStorage` and send the `join` message automatically.

The session data survives the restart (snapshot), so judges would be back in their session without any manual steps.
