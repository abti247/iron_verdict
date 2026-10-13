# Fake VPortal Server — Fidelity Assessment

**Date:** 2026-05-19 — originally written pre-staging, updated after the referee cross-check and the 2026-05-19 staging visit; cookie-name update and staging re-verification with v0.2.1 on 2026-10-13 (issue #101).
**Context:** End-to-end tests for the VPortal integration run against [`tests/e2e/fake_vportal.py`](../tests/e2e/fake_vportal.py), a small FastAPI app that mimics the subset of VPortal that Iron Verdict consumes. This document captures the pre-staging risk assessment and how each risk was resolved against real production-shape behavior.

**Companion reference:** the BVDK referee project at `github.com/franknitschke/referee` — specifically `server/vportal/vportalHelper.js`, `queries.js`, and `getCompetitionData.js`. The fake server and proxy were modeled after referee, and the worktree was cross-checked against it during implementation.

## Overall confidence: ~9.5 / 10

The integration was validated end-to-end against `staging-bvdk.vportal-online.de` on 2026-05-19: login, JWT decoding, cookie parsing, GraphQL query shapes, and the lifter-overlay normalizer all confirmed against production-shape data (lifter `B.D.`, club `V.F.V BRAUNSCHWEIG E.V.`, etc., rendered cleanly). Wrong-credentials handling (initially flagged as the one open item) was also resolved after a follow-up staging probe revealed the two-step rejection pattern.

The remaining ~5% covers the items in ["What we deliberately do not test"](#what-we-deliberately-do-not-test) below and any production-only response variations we couldn't see from staging traffic.

## What was validated at staging (2026-05-19)

| Area | Outcome |
|---|---|
| Auth flow shape (form-POST `/account/login` → `Set-Cookie: VPORTAL=…` → GET `/auth/token` with cookie → JSON with `access_token`) | ✅ Worked end-to-end |
| Login status code | Real VPortal returns **302** (not 200) on success — proxy correctly ignores status and reads cookie |
| Cookie name | `VPORTAL` confirmed — renamed to `__Host-VPORTAL` on staging by 2026-10-13, see [Cookie name](#cookie-name-vportal--__host-vportal---updated-2026-10-13) |
| `Authorization: Bearer <jwt>` for GraphQL | Works as expected |
| `exp` location | Real VPortal returns **no top-level `exp`** in `/auth/token`; `exp` lives inside the JWT payload — proxy decodes it correctly |
| GraphQL response shapes for `competitionGroupList`, `competitionStageList`, `competitionAthleteAttemptList` | All field paths in [`vportalClient.fetchActiveAttempt`](../src/iron_verdict/static/js/vportalClient.js) match production output verbatim |
| Polling cadence (server-clamped ≥2000ms) | Confirmed; no rate-limit pushback from staging during test runs |

## Pre-staging risks identified and how each was resolved

### Cookie name `VPORTAL` → `__Host-VPORTAL` — **✅ Updated 2026-10-13**

Pre-staging concern: spec hardcoded `"VPORTAL=" in part` for cookie extraction without referee confirmation.

Resolution (2026-05-19): confirmed in referee (`server/vportal/vportalHelper.js` does `cookieHeader.find(el => el.includes('VPORTAL'))`) and observed at staging — the `Set-Cookie` header from real VPortal did use `VPORTAL=` as the cookie name.

Update (2026-10-13, issue #101): login via Iron Verdict against `staging-bvdk.vportal-online.de` failed with 502 "VPortal did not return a session cookie". The maintainer's browser DevTools capture (screenshot, 2026-10-13) of a direct login on staging showed:

```
POST /account/login → 302 Found
Location: /dashboard
Set-Cookie: __Host-VPORTAL=<value>; expires=…; Max-Age=28800; path=/; secure; HttpOnly; SameSite=Lax
```

The session cookie is now named **`__Host-VPORTAL`**; `GET /auth/token` with it still returns JSON with `access_token` (checked in the same browser session). Production (`bvdk`/`oevk`) is expected to follow when VPortal rolls the release out there.

- **Proxy:** accepts both `__Host-VPORTAL` (preferred) and `VPORTAL`, and sends the cookie to `/auth/token` under the name it arrived with — works regardless of when production switches.
- **Fake server:** now emits the staging header verbatim in shape (`__Host-VPORTAL`, `Max-Age`, `secure`, `SameSite=Lax`, comma inside `expires=` kept) and `/auth/token` only accepts the cookie under the name `__Host-VPORTAL`. The E2E suite therefore exercises the new name; the legacy `VPORTAL` name stays covered by the backend tests in `tests/test_vportal_proxy.py`.
- **Not changed:** the login form is still sent as `multipart/form-data` without `submit=`, although the staging browser sends `application/x-www-form-urlencoded` with `submit=`. Maintainer decision (2026-10-13): multipart is proven against production by referee; change one thing at a time. **Confirmed 2026-10-13:** staging still accepts the multipart form (see verification below).

**Staging verification 2026-10-13 (v0.2.1, by the maintainer against `staging-bvdk.vportal-online.de`):**
- Login with a valid account succeeds (`__Host-VPORTAL` cookie accepted and exchanged at `/auth/token`; multipart form accepted).
- The display overlay shows the current lifter's data from polling.
- Wrong password → the modal shows "Anmeldung fehlgeschlagen – Benutzername oder Passwort prüfen." — the modal message for the proxy's 401, not the 502 error; the two-step rejection pattern still holds with the new cookie name.
- Valid login, disconnect, then wrong password → same failure message; no session carried over from the first login.
- Not verified: production (`bvdk`/`oevk`) — still unknown whether it already sends `__Host-VPORTAL`; the `VPORTAL` fallback is covered by backend tests only.

### Set-Cookie parsing fragility (comma in `expires=`) — **✅ Resolved**

Pre-staging concern: the proxy split the raw `Set-Cookie` header on `,`. Real cookies can contain commas inside `expires=Wed, 21 Oct 2025 …`, which would corrupt the split.

Resolution: replaced the hand-rolled splitter with `login_resp.cookies.get("VPORTAL")` — httpx delegates to Python's stdlib `http.cookies` parser, which handles attribute-internal commas correctly. The fake server emits a stress-test cookie with a comma inside its `expires=` to keep this protected in CI.

### `follow_redirects=False` assumes login responds 200 — **✅ Resolved**

Pre-staging concern: the proxy treated non-200 / non-302 login responses as failure, but referee never inspects the login status code; real VPortal might 302 on success.

Resolution: dropped the status-code short-circuit entirely. The proxy now only checks for the presence of a session cookie (`VPORTAL`, since 2026-10-13 also `__Host-VPORTAL`) in the login response — matching referee's behavior. Confirmed at staging: real VPortal returns **302 + cookie + `Location`**, and our proxy handles it correctly.

### GraphQL error envelopes — **✅ Mostly resolved**

Pre-staging concern: the fake returned either canonical `{data: ...}` or `{errors: [...]}` with a 400. Real VPortal might do something different.

Resolution: staging returned canonical `{data: ...}` shapes for all four queries — exactly what the fake emits. We never received an error envelope from staging, so the specific shape of `errors[]` is still untested in practice — but the client's `?.` chains and the normalizer's `?? ''` fallbacks render gracefully (empty fields) on any unexpected null/undefined, which is the desired behavior anyway.

### Auth-failure status codes (wrong-credentials UX) — **✅ Resolved**

Pre-staging concern: the proxy treated only HTTP 401/403 on `/account/login` as "bad credentials." If real VPortal returned anything else on wrong creds (e.g., 200 + HTML), the proxy would surface a confusing "VPortal upstream error" instead of "wrong password."

Resolution: real VPortal turned out to use a **two-step rejection** — verified at staging 2026-05-19:
1. `POST /account/login` with wrong credentials still returns **200 + `Set-Cookie: VPORTAL=…`** (a pre-auth cookie marking that the form was processed).
2. `GET /auth/token` with that pre-auth cookie rejects via **302 redirect** to `/login?error=1` (not 401 as first hypothesised). httpx with `follow_redirects=False` (the default for `AsyncClient.get`) returns the 302 directly.

The proxy maps 302/401/403 from `/auth/token` to its own **401 "Invalid VPortal credentials"**, which the client modal already renders as "Login failed — check username and password." Any other non-200 status from `/auth/token` surfaces as **424** with `detail: {"reason": "token_exchange_failed", "upstream_status": <n>}` and a `vportal_login_failed` warning (424 instead of 502 since issue #100: Cloudflare replaced the 502 body, so the cause never reached the browser). Note that 302/401/403 write no log line — a role or permission problem that VPortal reports as a 302 looks like a wrong password.

### Logging whitelist (post-deployment discovery) — **✅ Resolved**

While diagnosing the above, found that [`logging_config.py`](../src/iron_verdict/logging_config.py) had an `_EXTRA_FIELDS` whitelist that silently dropped any `logger.warning(..., extra={...})` field not listed in it. Every VPortal log statement was emitting context-less log lines (no `host`, no `upstream_status`, no `kind`, etc.). Added the VPortal-specific keys to the whitelist. Worth a follow-up refactor to either drop the whitelist (emit all extras) or document the field-registration requirement somewhere visible — silent-drop logging is unkind to debugging.

### Cookie-jar leakage across login attempts — **✅ Resolved (post-staging discovery)**

Pre-staging concern: not on the original list. Discovered during a follow-up staging attempt to capture the wrong-credentials response shape.

The reproduction: type deliberately-wrong credentials into the connect modal *after* a successful login earlier in the same Railway container's lifetime. The login succeeded anyway, returning a JWT for the *previous* operator.

Root cause: the proxy used a single module-level `httpx.AsyncClient` for everything, and `httpx.AsyncClient` keeps a cookie jar that persists across requests. After the first successful login seeded `VPORTAL=<valid>` into the jar, every subsequent login's outbound POST included that cookie in the `Cookie:` header. Real VPortal treated the request as a session refresh — ignoring the form credentials in the body — and responded with a 302 + refreshed cookie for the previous operator. The proxy then completed `/auth/token` with that cookie and handed the previous operator's JWT back to a user who never had valid credentials.

Severity: session-bleed. Two operators sharing the same Railway deployment could inherit each other's VPortal sessions.

Resolution: introduced `_make_login_client()` factory that returns a fresh `httpx.AsyncClient` per login flow, used inside `async with`. Cookie jar is scoped to a single login's two HTTP calls; nothing persists between logins. The shared `_http_client` remains for `/graphql` (bearer auth, no cookies). Regression test `test_login_does_not_leak_cookie_jar_between_calls` asserts no `VPORTAL` cookie appears on a second outbound login after a successful first one.

### `exp` field presence — **✅ Resolved**

Pre-staging concern: spec assumed `/auth/token` returns a top-level `exp` field. Referee instead does `jwt.decode(access_token).exp`, suggesting real VPortal puts `exp` inside the JWT only.

Resolution: implemented `_extract_jwt_exp` in the proxy — base64url-decode the JWT's middle segment, read `exp` from the payload, fall back to top-level `exp` for safety. Confirmed at staging: real `/auth/token` returns only `{access_token: ...}` with no top-level `exp`; the JWT payload contains a future `exp` timestamp, which our decoder extracts correctly.

## What we deliberately do not test

- **Concurrent logins from the same operator account.** Real VPortal probably tracks active sessions; if Iron Verdict's proxy login invalidates a parallel operator session somewhere, that's bad. We don't simulate it.
- **Rate limits on the real `/graphql` endpoint.** The fake server has none. Real VPortal might 429 us if polling cadence is too aggressive — but we already clamp to ≥2000ms server-side, so this is low risk. Confirmed at staging: no rate-limiting observed during a typical-length smoke test.
- **Token refresh.** Out of scope per the spec (operator re-logs in). The fake plays along: it doesn't expire tokens unless `force_token_invalid` is flipped.
- **Multiple stages with one of them marked inactive.** Fake returns one stage in one state. Real VPortal might return stages with various visibility flags we don't filter on.
- **Athletes without a `bodyWeightCategory` or `ageCategory`.** Real BVDK youth flights sometimes use different category models. Our normalizer renders empty strings for missing fields — visually fine but not tested.

## Capture procedure for any future smoke test

Open browser DevTools → Network while stepping through the flow. The items below were all confirmed at the 2026-05-19 staging visit; keep capturing them at future runs to detect drift if VPortal changes its responses:

1. The raw `Set-Cookie` header value from `/account/login` (was: `VPORTAL=…` on 2026-05-19, `__Host-VPORTAL=…` on 2026-10-13).
2. The HTTP status code on `/account/login` on success (was: 302 at staging).
3. The full JSON body of `/auth/token` (was: `{access_token: "..."}` only, no top-level `exp`).
4. The full JSON body of one `/graphql` call. Field paths the normalizer reads: `data.competitionAthleteAttemptList.competitionAthleteAttempts[0].{attempt, discipline, weight, competitionAthlete.{firstName, lastName, club.name, bodyWeightCategory.name, ageCategory.name}}`.
5. (Optional) Deliberately log in with wrong credentials. The proxy should return **401 "Invalid VPortal credentials"** to the browser, mapped from upstream `/auth/token`'s 401. If you see anything else, the two-step rejection pattern has changed.
6. If a login fails with anything other than 401: the browser gets **424** with `detail.reason` (`no_session_cookie`, `token_exchange_failed` + `upstream_status`, `missing_access_token`, `unreachable`), and the server log has one `vportal_login_failed` entry with the statuses and `Location` headers of `/account/login` and `/auth/token`, the token `content_type` and the **names** of the cookies `/account/login` set. Record those values here — they show what real VPortal sent without needing DevTools on the operator's device.

If any of (1)–(6) differs from what we saw at the 2026-05-19 staging visit, VPortal has changed its API and our code likely needs adjustment — auth-layer shape mismatches go in [`vportal_proxy.py`](../src/iron_verdict/vportal_proxy.py), response-shape mismatches go in [`vportalClient.js`](../src/iron_verdict/static/js/vportalClient.js) `fetchActiveAttempt`.
