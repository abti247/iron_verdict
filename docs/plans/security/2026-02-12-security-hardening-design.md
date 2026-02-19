# Security Hardening Design — JudgeMe

**Date:** 2026-02-12
**Based on:** docs/security-review.md
**Scope:** All 16 issues except M2 (vote redaction — not needed given session code is the trust boundary)

---

## Approach

Harden the session code itself rather than adding a separate PIN system (C3). Pair with rate limiting to make brute-force infeasible in practice.

Fix order: 5 batches, each a separate PR.

---

## Batch A — Trivial one-liners (zero risk)

| Issue | Change |
|---|---|
| C4 | Replace `random.choices()` with `secrets.choice()` in `session.py`. Increase code length from 6 to 8 chars. |
| C5 | Gate `reload` on env var in `run.py`: `reload = os.getenv("ENV") == "development"` |
| H4 | Validate `color` in `main.py` against `{"white", "red", "blue", "yellow"}` before calling `lock_vote`. Return error and `continue` on invalid value. |
| H2 | After reading session code from `URLSearchParams` in `index.html`, call `history.replaceState({}, '', window.location.pathname)` to remove it from the address bar. |
| M4 | Pin Alpine.js to `@3.14.1` and add `integrity` + `crossorigin` SRI attributes. Compute hash once with `openssl`. |

No new dependencies. No schema changes.

---

## Batch B — Server internals

| Issue | Change |
|---|---|
| C2 | Add `lifespan` startup task in `main.py`. Runs every 30 min, calls `session_manager.cleanup_expired()`. Add `cleanup_expired()` to `SessionManager` — deletes sessions where `last_activity` is older than `SESSION_TIMEOUT_HOURS`. |
| M3 | Add `asyncio.Lock()` to `SessionManager`. Acquire in `create_session`, `lock_vote`, `reset_for_next_lift`. Pattern already exists in `ConnectionManager`. |
| L2 | On WebSocket join, count `display` clients in session and reject if over cap (default: 20). Return clear error to client. |

No new dependencies.

---

## Batch C — Abuse prevention

| Issue | Change |
|---|---|
| C1 | Add `slowapi`. Rate-limit `POST /api/sessions` to 10 requests/hour/IP. Return HTTP 429 on breach. |
| H3 | In WebSocket handler loop, track message counter + timestamp per connection. Disconnect (code 1008) if client exceeds 20 messages/second. No external library. |
| M1 | At top of WebSocket handler, check `Origin` header against `ALLOWED_ORIGIN` env var. Close (code 1008) on mismatch. Set `ALLOWED_ORIGIN=*` for local dev. |

One new dependency: `slowapi`.

---

## Batch D — Hardening

| Issue | Change |
|---|---|
| C3 | Audit `index.html`: remove session code from the **display** view only. All judge roles (head, left, right, center) may still see it. |
| H1 | No code change. Add `docs/deployment.md` recommending Caddy as reverse proxy for automatic Let's Encrypt TLS. |
| L1 | Add FastAPI middleware that injects 5 security headers: `Content-Security-Policy` (allowlist `cdn.jsdelivr.net`), `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Strict-Transport-Security`. Tighten CSP to `script-src 'self'` after Alpine.js is self-hosted. |

---

## Batch E — Observability

| Issue | Change |
|---|---|
| H5 | Add `logging` with JSON formatter to `main.py`. Log at `INFO`: session created/ended, role joined/disconnected (with client IP from `X-Forwarded-For`), vote locked, timer actions. Output to stdout for process supervisor to redirect. |

No new dependencies (stdlib only).

---

## Summary

| Batch | Issues | New deps |
|---|---|---|
| A | C4, C5, H4, H2, M4 | none |
| B | C2, M3, L2 | none |
| C | C1, H3, M1 | `slowapi` |
| D | C3, H1, L1 | none |
| E | H5 | none |
