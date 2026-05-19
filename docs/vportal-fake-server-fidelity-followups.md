# VPortal Fake-Server Fidelity — Follow-up Actions

**Date:** 2026-05-19
**Companion to:** [`vportal-fake-server-fidelity.md`](vportal-fake-server-fidelity.md)
**Origin:** Cross-check of the worktree against `github.com/franknitschke/referee` (`server/vportal/vportalHelper.js`, `server/vportal/queries.js`, `server/vportal/getCompetitionData.js`).

The original fidelity doc flagged several risks as "guesses pending staging access." Reading referee directly resolves four of them — referee is itself a working integration against real VPortal, so referee's behavior is ground truth, not a guess. Only one item still requires staging verification.

## Verified against referee — no change needed

- **Cookie name is `VPORTAL`** — referee hardcodes `cookieHeader.find((el) => el.includes('VPORTAL'))`. The original doc rated this a guess; it isn't.
- **GraphQL variable shapes** — `competitionAthleteAttemptListParams` with `filter.{competitionGroupId, competitionStageId}` and `competitionGroupListParams` with `filter.{competitionStageId, active: true}` match referee verbatim. `competitionGroupId` is passed as an array in both. Confidence raises from 7/10 to ~9/10.
- **Workflow shape** — referee fetches groups + athletes in parallel; we go sequential. Functionally equivalent, slightly slower per poll. Not worth changing.

## Fix now — four aligned changes

Apply in one PR. All four are referee-aligned and locally testable.

| # | Proxy change (`src/iron_verdict/vportal_proxy.py`) | Fake-server change (`tests/e2e/fake_vportal.py`) | Rationale |
|---|---|---|---|
| 1 | Send login body as **multipart/form-data**, not urlencoded. Use `httpx` `files={"identity": (None, body.identity), "credential": (None, body.credential)}` to force multipart encoding. Drop the manual `urlencode(...)` and `content-type: application/x-www-form-urlencoded`. | Replace urlencoded parsing in `POST /account/login` with FastAPI `Form(...)` params (handles both encodings, so the test stays valid). | Referee builds a `FormData` and posts it; Node fetch sends `multipart/form-data; boundary=…`. Real VPortal was integrated against multipart and works in production. |
| 2 | Stop hand-rolling the `Set-Cookie` split. Use `login_resp.cookies.get("VPORTAL")` — httpx parses it correctly, including cookies with commas inside `expires=…`. | No change to the happy-path cookie. See "tighten the fake" below for a stress-test addition. | Our current `split(',')` corrupts on any cookie attribute containing a comma. Referee uses `headers.getSetCookie()` (array-returning); httpx's parsed cookies are the Python equivalent. |
| 3 | Extract `exp` by **decoding the JWT payload** (`base64url`-decode the middle `.`-separated segment, `json.loads`, read `exp`). Keep a fallback to top-level `token_payload.get("exp")` for safety. | Make `access_token` a real JWT-shaped string (`header.payload.signature` with a base64-encoded `{"exp": 9999999999}` payload). Drop the top-level `exp` from the `/auth/token` response. | Referee does `jwt.decode(access_token).exp` — strong evidence real VPortal's response envelope doesn't carry `exp` and we need to look inside the JWT. |
| 4 | Drop the `if login_resp.status_code in (401, 403)` and `if login_resp.status_code >= 500` short-circuits on the login response. Just attempt cookie extraction; if no cookie is returned, raise then. | No change. | Referee never inspects the login status code. Matching this removes the "wrong password surfaces as 502 upstream error" failure mode regardless of what status real VPortal returns on bad creds. UX for genuine wrong-credentials cases is the one remaining staging question (below). |

## Tighten the fake while you're in there

Cheap fidelity wins that make the fake harder to pass with wrong code:

- **Reject urlencoded** in the fake's `/account/login` (return 415 or an empty/no-cookie response) so anyone reintroducing the urlencoded path gets a red test.
- **Return 302 + Set-Cookie + Location** on successful login instead of 200. Referee uses `redirect: 'manual'`, implying real VPortal redirects. This stress-tests the "we don't care about status code" change (#4 above).
- **Emit a `Set-Cookie` with `expires=Wed, 21 Oct 2099 07:28:00 GMT`** (comma inside the date) so the old `split(',')` parser would fail the test and the new `response.cookies["VPORTAL"]` path passes.

## Still requires staging — one item only

**Wrong-credentials response shape.** Referee handles bad creds by silently breaking (cookie extraction throws, returns `null`). After change #4 above, our proxy will surface that as "no session cookie returned" — functionally correct but poor UX. To map bad creds to a clean `401 Invalid VPortal credentials` we need to know what real VPortal actually returns on wrong input: 401, 200-with-HTML, 302-to-`/login?error=1`, or something else.

**How to capture during the staging visit:** open DevTools → Network, deliberately log in with wrong credentials once, screenshot or "Copy as cURL" the `/account/login` row showing status code + response body. That single capture resolves it. Implement as a follow-up after the main four-change PR.

## Out of scope (unchanged from original doc)

- Concurrent operator sessions
- Real-VPortal rate limits on `/graphql` (we already clamp polling to ≥2000ms)
- Token refresh (spec says operator re-logs in on expiry)
- Stage visibility flags, missing `bodyWeightCategory` / `ageCategory`
