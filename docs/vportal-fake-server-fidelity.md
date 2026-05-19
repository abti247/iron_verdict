# Fake VPortal Server — Fidelity Assessment

**Date:** 2026-05-19 (originally written before the referee cross-check)
**Context:** End-to-end tests for the VPortal integration run against [`tests/e2e/fake_vportal.py`](../tests/e2e/fake_vportal.py), a small FastAPI app that mimics the subset of VPortal that Iron Verdict consumes. This document captures how confident we are that the fake matches real BVDK / ÖVK / staging VPortal behavior, what's likely wrong, and where to look first when running against the real instance.

**Companion reference:** the BVDK referee project at `github.com/franknitschke/referee`. The spec calls out `server/vportal/queries.js` (and presumably an auth module nearby) as the source of truth that the spec — and therefore the fake — was modeled after.

> **Update — referee cross-check performed.** A separate review session compared the worktree against `server/vportal/vportalHelper.js`, `queries.js`, and `getCompetitionData.js` in the referee repo. Four follow-up changes were implemented and merged: multipart login, httpx-parsed cookies, JWT-payload `exp` extraction, and removal of the upstream-login status-code short-circuit. The fake was tightened in the same pass (rejects urlencoded, returns 302 + cookie with comma in `expires=`, emits real JWT-shaped tokens). **One open item** remains: the wrong-credentials response shape — currently surfaces as 502 "no session cookie" rather than a clean 401 until we capture real VPortal's actual wrong-creds response.

## Overall confidence: ~9 / 10 (after referee cross-check)

The auth-layer items previously rated 6/10 — cookie name, GraphQL variable shapes, Set-Cookie parsing fragility, login redirect behavior, JWT `exp` location — are now confirmed against referee or explicitly stress-tested by the fake. The remaining ~10% is the wrong-credentials UX and any production-only response variations we can't see without staging traffic.

The structural shape is right and was lifted from a working integration. The pieces most likely to break against real VPortal are the Set-Cookie parsing, the assumption that login does not redirect, and the GraphQL error-envelope shape. These are not protected by any of our tests because the fake server emits clean canonical responses.

## What's likely correct

| Area | Why we believe it | Confidence |
|---|---|---|
| Auth flow shape (form POST `/account/login` → `Set-Cookie: VPORTAL=…` → GET `/auth/token` with cookie → JSON `{access_token, exp}`) | Copied from the BVDK referee's integration, which is used at real BVDK competitions | 8 / 10 |
| `Authorization: Bearer <jwt>` for GraphQL calls | Standard pattern; nothing federation-specific | 9 / 10 |
| GraphQL response shape for `competitionAthleteAttemptList[0].competitionAthlete.{firstName, lastName, club.name, bodyWeightCategory.name, ageCategory.name}` | Query selection set copied verbatim from referee's `queries.js`; server presumably returns what was asked for | 7 / 10 |
| GraphQL response shape for `competitionGroupList`, `competitionStageList` | Same provenance | 7 / 10 |

## What's a guess

### Cookie name `VPORTAL`
The spec says the session cookie is named `VPORTAL`. We assume this from the spec text; we have not grepped the referee repo to confirm. The proxy hardcodes `"VPORTAL=" in part` when parsing `Set-Cookie`. If the real cookie is named differently (`vportal_session`, `BVDKAUTH`, etc.) login silently fails — the cookie extraction returns `None` and the proxy raises 502 "VPortal did not return a session cookie."

**To verify:** open DevTools → Network → log in to real VPortal manually → inspect the `Set-Cookie` header of the `/account/login` response.

### Set-Cookie parsing is fragile
[`vportal_proxy.py`](../src/iron_verdict/vportal_proxy.py) splits the raw `Set-Cookie` header on `,`. Real cookies can contain commas inside `expires=Wed, 21 Oct 2025 …` or `domain=…` attributes, which would corrupt the split. Our fake server emits a single, clean `VPORTAL=fake-cookie; Path=/; HttpOnly` with no commas, so this code path is never stressed by tests. **This is the most likely production failure mode.**

**To verify:** during the staging smoke test, inspect the real `Set-Cookie` header. If it contains a comma anywhere (typical for `expires=…`), the proxy's parser will misread the cookie value.

**Fix if it breaks:** switch to `response.cookies["VPORTAL"]` or parse `Set-Cookie` via `http.cookies.SimpleCookie`. Don't roll our own splitter.

### `follow_redirects=False` assumes login responds 200
The proxy passes `follow_redirects=False` to the login POST and expects a 200 response with the cookie set. Some real auth flows respond 302 + `Set-Cookie` + `Location: /dashboard`. If real VPortal does that:

- httpx with `follow_redirects=False` returns the 302 response directly.
- Our code checks `if login_resp.status_code in (401, 403)` (no — it's 302) and `if login_resp.status_code >= 500` (no — it's 302). It falls through to cookie extraction.
- If the 302 also includes `Set-Cookie`, extraction succeeds and we proceed. If the cookie is only set on the redirected response, we get a 502.

**To verify:** during the smoke test, check whether real VPortal's `/account/login` returns 200 or 302 on success. Our test never exercises the 302 case.

### GraphQL error envelopes are untested
The fake server returns either canonical `{"data": {...}}` or `{"errors": [...]}` with a 400. Real VPortal might:

- Return 200 with `{"errors": [...], "data": null}` (standard GraphQL pattern; our client currently does `response.data?.profile?…` which silently returns `undefined` and renders blank corners — graceful but not informative).
- Return partial data: e.g., `competitionAthlete.club` is `null` on an unaffiliated athlete. Our normalizer handles this via `?? ''`, so the corner shows empty club — probably fine, but never tested.

**To verify:** during the smoke test, watch the GraphQL response shapes in Network. If any field is `null` where the fake returns a populated object, the UI may render strangely.

### Auth-failure status codes
Our fake returns 401 on bad credentials. Real VPortal might:

- Return 200 with HTML containing an error message (typical for traditional server-rendered login forms).
- Return 200 + JSON `{"error": "invalid_credentials"}`.
- Redirect 302 to `/login?error=1`.

The proxy only treats 401/403 as "bad credentials." Anything else with a non-500 status flows into cookie extraction, fails to find a cookie, and surfaces as 502 "VPortal did not return a session cookie" — confusing UX (operator sees "VPortal upstream error" instead of "wrong password").

**To verify:** during the smoke test, deliberately enter wrong credentials once and watch the response code.

### `exp` field presence
The fake returns `{"access_token": "fake-jwt", "exp": 9999999999}`. The proxy passes `exp` through to the client. The client gates polling on `Date.now() / 1000 >= stored.exp`.

If real VPortal's `/auth/token` doesn't include an `exp` field — or returns the JWT's expiry as part of the JWT payload only — `stored.exp` is `undefined` and the client never proactively detects expiry. It still catches 401s from upstream, so expired tokens are detected; the proactive check just becomes a no-op.

**To verify:** check the real `/auth/token` response body. If there's no top-level `exp`, the proxy could either (a) decode the JWT to extract `exp`, or (b) leave the client to fall back to 401-detection only.

## What we deliberately do not test

- **Concurrent logins from the same operator account.** Real VPortal probably tracks active sessions; if Iron Verdict's proxy login invalidates a parallel operator session somewhere, that's bad. We don't simulate it.
- **Rate limits on the real `/graphql` endpoint.** The fake server has none. Real VPortal might 429 us if polling cadence is too aggressive — but we already clamp to ≥2000ms server-side, so this is low risk.
- **Token refresh.** Out of scope per the spec (operator re-logs in). The fake plays along: it doesn't expire tokens unless `force_token_invalid` is flipped.
- **Multiple stages with one of them marked inactive.** Fake returns one stage in one state. Real VPortal might return stages with various visibility flags we don't filter on.
- **Athletes without a `bodyWeightCategory` or `ageCategory`.** Real BVDK youth flights sometimes use different category models. Our normalizer renders empty strings for missing fields — visually fine but not tested.

## Recommendation for any future smoke test

Open browser DevTools → Network while stepping through the flow. Capture these for later cross-checking with the referee codebase:

1. The raw `Set-Cookie` header value from `/account/login`. Compare to what our parser expects.
2. The HTTP status code on `/account/login` on success — is it 200 or 302?
3. The full JSON body of `/auth/token`. Confirm `access_token` + `exp` are top-level.
4. The full JSON body of one `/graphql` call. Confirm the `data.competitionAthleteAttemptList.competitionAthleteAttempts[0]` shape matches the fields our normalizer reads.

If any of (1)–(4) differs from the fake, the production code needs adjustment — usually in [`vportal_proxy.py`](../src/iron_verdict/vportal_proxy.py) for auth-layer shape mismatches, in [`vportalClient.js`](../src/iron_verdict/static/js/vportalClient.js) `fetchActiveAttempt` for response-shape mismatches.

## Follow-up review against the referee repo

In a separate review session with `github.com/franknitschke/referee` cloned locally, verify:

- `server/vportal/auth.js` (or equivalent) — confirms cookie name and login status code expectations.
- `server/vportal/queries.js` — confirms the GraphQL selection sets we copied are identical to what referee uses today.
- Any retry/refresh logic referee has that we deliberately don't (because the spec says operator re-logs in on expiry).
- Whether referee parses `Set-Cookie` via a more robust method than `split(',')` — if so, copy that pattern.

The goal of that review is to either raise the confidence on this document to ~9/10 (claims verified) or generate a list of corrective edits before the first real-event test.
