# Design: P2 — WebSocket Connection ID

## Goal

Add a `conn_id` field to all WebSocket-related log lines so a single judge's full connection lifecycle (join → vote → disconnect) can be traced in isolation, even when multiple clients are active in the same session.

## Approach

Generate a random 16-char hex ID (`secrets.token_hex(8)`) at the top of `websocket_endpoint` and pass it as `extra` in every log call within that handler. Register `conn_id` in `_EXTRA_FIELDS` so `JsonFormatter` includes it automatically.

## Files Changed

- `src/iron_verdict/logging_config.py` — add `conn_id` to `_EXTRA_FIELDS`
- `src/iron_verdict/main.py` — generate `conn_id` at WS connect, add to all `extra={}` dicts in `websocket_endpoint`

## Coverage

Log events that gain `conn_id`:
- `origin_rejected`
- `message_flood_disconnect`
- `role_join_failed`
- `role_joined`
- `vote_locked`
- `role_disconnected`
- `ws_close_failed`

HTTP log lines (`session_created`, `unhandled_exception`) are left out — they're one-shot with no lifecycle to trace.

## Out of Scope

- HTTP request IDs
- `contextvars` / middleware
- Any new dependencies (`secrets` already imported)
