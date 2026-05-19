# Fake VPortal Server — Fidelity Assessment

**Date:** 2026-05-19 — originally written pre-staging, updated after the referee cross-check and the 2026-05-19 staging visit.
**Context:** End-to-end tests for the VPortal integration run against [`tests/e2e/fake_vportal.py`](../tests/e2e/fake_vportal.py), a small FastAPI app that mimics the subset of VPortal that Iron Verdict consumes. This document captures the pre-staging risk assessment, how each risk was resolved, and what (single) item remains open against real production VPortal.

**Companion reference:** the BVDK referee project at `github.com/franknitschke/referee` — specifically `server/vportal/vportalHelper.js`, `queries.js`, and `getCompetitionData.js`. The fake server and proxy were modeled after referee, and the worktree was cross-checked against it during implementation.

## Overall confidence: ~9.5 / 10

The integration was validated end-to-end against `staging-bvdk.vportal-online.de` on 2026-05-19: login, JWT decoding, cookie parsing, GraphQL query shapes, and the lifter-overlay normalizer all confirmed against production-shape data (lifter `B.D.`, club `V.F.V BRAUNSCHWEIG E.V.`, etc., rendered cleanly).

One item remains open: the wrong-credentials UX (see ["Still open"](#still-open) below).

## What was validated at staging (2026-05-19)

| Area | Outcome |
|---|---|
| Auth flow shape (form-POST `/account/login` → `Set-Cookie: VPORTAL=…` → GET `/auth/token` with cookie → JSON with `access_token`) | ✅ Worked end-to-end |
| Login status code | Real VPortal returns **302** (not 200) on success — proxy correctly ignores status and reads cookie |
| Cookie name | `VPORTAL` confirmed |
| `Authorization: Bearer <jwt>` for GraphQL | Works as expected |
| `exp` location | Real VPortal returns **no top-level `exp`** in `/auth/token`; `exp` lives inside the JWT payload — proxy decodes it correctly |
| GraphQL response shapes for `competitionGroupList`, `competitionStageList`, `competitionAthleteAttemptList` | All field paths in [`vportalClient.fetchActiveAttempt`](../src/iron_verdict/static/js/vportalClient.js) match production output verbatim |
| Polling cadence (server-clamped ≥2000ms) | Confirmed; no rate-limit pushback from staging during test runs |

## Pre-staging risks identified and how each was resolved

### Cookie name `VPORTAL` — **✅ Resolved**

Pre-staging concern: spec hardcoded `"VPORTAL=" in part` for cookie extraction without referee confirmation.

Resolution: confirmed in referee (`server/vportal/vportalHelper.js` does `cookieHeader.find(el => el.includes('VPORTAL'))`) and observed at staging — the `Set-Cookie` header from real VPortal does use `VPORTAL=` as the cookie name.

### Set-Cookie parsing fragility (comma in `expires=`) — **✅ Resolved**

Pre-staging concern: the proxy split the raw `Set-Cookie` header on `,`. Real cookies can contain commas inside `expires=Wed, 21 Oct 2025 …`, which would corrupt the split.

Resolution: replaced the hand-rolled splitter with `login_resp.cookies.get("VPORTAL")` — httpx delegates to Python's stdlib `http.cookies` parser, which handles attribute-internal commas correctly. The fake server emits a stress-test cookie with a comma inside its `expires=` to keep this protected in CI.

### `follow_redirects=False` assumes login responds 200 — **✅ Resolved**

Pre-staging concern: the proxy treated non-200 / non-302 login responses as failure, but referee never inspects the login status code; real VPortal might 302 on success.

Resolution: dropped the status-code short-circuit entirely. The proxy now only checks for the presence of a `VPORTAL` cookie in the login response — matching referee's behavior. Confirmed at staging: real VPortal returns **302 + cookie + `Location`**, and our proxy handles it correctly.

### GraphQL error envelopes — **✅ Mostly resolved**

Pre-staging concern: the fake returned either canonical `{data: ...}` or `{errors: [...]}` with a 400. Real VPortal might do something different.

Resolution: staging returned canonical `{data: ...}` shapes for all four queries — exactly what the fake emits. We never received an error envelope from staging, so the specific shape of `errors[]` is still untested in practice — but the client's `?.` chains and the normalizer's `?? ''` fallbacks render gracefully (empty fields) on any unexpected null/undefined, which is the desired behavior anyway.

### Auth-failure status codes (wrong-credentials UX) — **🟡 Still open**

See ["Still open"](#still-open) below.

### `exp` field presence — **✅ Resolved**

Pre-staging concern: spec assumed `/auth/token` returns a top-level `exp` field. Referee instead does `jwt.decode(access_token).exp`, suggesting real VPortal puts `exp` inside the JWT only.

Resolution: implemented `_extract_jwt_exp` in the proxy — base64url-decode the JWT's middle segment, read `exp` from the payload, fall back to top-level `exp` for safety. Confirmed at staging: real `/auth/token` returns only `{access_token: ...}` with no top-level `exp`; the JWT payload contains a future `exp` timestamp, which our decoder extracts correctly.

## Still open

### Wrong-credentials UX

The proxy no longer inspects the login status code (referee-aligned, as required by the 302-on-success behavior real VPortal exhibits). The side-effect: bad credentials produce no `VPORTAL` cookie, so the proxy surfaces them as **502 "VPortal did not return a session cookie"** rather than a clean **401 "Invalid VPortal credentials"**. Functionally correct but confusing UX — an operator typing the wrong password sees an "upstream error" instead of "wrong password."

**Why it's still open:** resolving cleanly requires knowing what real VPortal returns on bad credentials. Possibilities:
- HTTP 401
- HTTP 200 with HTML containing an error message (traditional server-rendered login form)
- HTTP 200 + JSON `{"error": "invalid_credentials"}`
- HTTP 302 to `/login?error=1`

We haven't captured the real response because the staging visit successfully logged in on the first attempt — we never sent a deliberately-wrong password.

**How to resolve:** during any future staging session, deliberately enter wrong credentials once. In DevTools → Network → `/account/login` row → grab the status code and response body, paste into a follow-up issue. Then add a branch in [`vportal_proxy.login`](../src/iron_verdict/vportal_proxy.py) that maps the observed shape back to a 401 with `"Invalid VPortal credentials"`.

Total work to resolve: ~5 lines of code once we have the capture.

## What we deliberately do not test

- **Concurrent logins from the same operator account.** Real VPortal probably tracks active sessions; if Iron Verdict's proxy login invalidates a parallel operator session somewhere, that's bad. We don't simulate it.
- **Rate limits on the real `/graphql` endpoint.** The fake server has none. Real VPortal might 429 us if polling cadence is too aggressive — but we already clamp to ≥2000ms server-side, so this is low risk. Confirmed at staging: no rate-limiting observed during a typical-length smoke test.
- **Token refresh.** Out of scope per the spec (operator re-logs in). The fake plays along: it doesn't expire tokens unless `force_token_invalid` is flipped.
- **Multiple stages with one of them marked inactive.** Fake returns one stage in one state. Real VPortal might return stages with various visibility flags we don't filter on.
- **Athletes without a `bodyWeightCategory` or `ageCategory`.** Real BVDK youth flights sometimes use different category models. Our normalizer renders empty strings for missing fields — visually fine but not tested.

## Capture procedure for any future smoke test

Open browser DevTools → Network while stepping through the flow. The items below were all confirmed at the 2026-05-19 staging visit; keep capturing them at future runs to detect drift if VPortal changes its responses:

1. The raw `Set-Cookie` header value from `/account/login`.
2. The HTTP status code on `/account/login` on success (was: 302 at staging).
3. The full JSON body of `/auth/token` (was: `{access_token: "..."}` only, no top-level `exp`).
4. The full JSON body of one `/graphql` call. Field paths the normalizer reads: `data.competitionAthleteAttemptList.competitionAthleteAttempts[0].{attempt, discipline, weight, competitionAthlete.{firstName, lastName, club.name, bodyWeightCategory.name, ageCategory.name}}`.
5. **(Still useful):** deliberately log in with wrong credentials once and capture the response status + body. That resolves the one outstanding open item above.

If any of (1)–(4) differs from what we saw at the 2026-05-19 staging visit, VPortal has changed its API and our code likely needs adjustment — auth-layer shape mismatches go in [`vportal_proxy.py`](../src/iron_verdict/vportal_proxy.py), response-shape mismatches go in [`vportalClient.js`](../src/iron_verdict/static/js/vportalClient.js) `fetchActiveAttempt`.
