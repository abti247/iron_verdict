# Project Overview

**Iron Verdict** - a web app for powerlifting competition judging.

The goal of the app is to provide an easy access to a tool for powerlifting judging.

## Product Requirements
- **Simple, intuitive operation** for judges and display operators. They use the app under time pressure at a live competition, often on unfamiliar devices — no hidden steps, no ambiguous states.
- **Live competition: no unnecessary waiting, no outages.** Every change is weighed against "could this delay or break a running competition?"

## Critical Path
The critical path is everything from the moment a judge or a display has joined a session: voting, timer, result display, reconnection, page reload.

Rules for any change touching the critical path:
- **No external runtime dependencies** (CDNs, third-party services) in the critical path. Venue Wi-Fi may block or lose them.
- **No message may be dropped silently.** The user always sees the real state (e.g. a vote is only shown as confirmed once the server confirmed it; a lost connection is visible).
- **Every change needs an E2E test of the user-visible flow.** For network-related changes this includes a connection-loss scenario (drop, reconnect, reload).
- **Test each behavior at the cheapest level that can see it** — E2E only for what a browser alone can show. What that means in practice, and why: `docs/testing.md`, "Conventions".
- **No artificial delays** (`setTimeout`, sleeps, debounces) without a written justification in the code or PR.

## VPortal Protection
The VPortal integration (BVDK/ÖVK competition-management software) is hard to verify: access to the real BVDK staging environment is **not permanently available**, so the fake-server tests are the safety net.

Protected files:
- `src/iron_verdict/vportal_proxy.py`
- `src/iron_verdict/static/js/vportalClient.js`
- `src/iron_verdict/static/js/vportalQueries.js`
- `src/iron_verdict/static/js/vportalStore.js`
- VPortal parts of `src/iron_verdict/static/index.html`, `src/iron_verdict/static/js/app.js` (vportal store registration) and `src/iron_verdict/static/js/screens/landingScreen.js` (staging flag)
- Every `vportal.*` call in `src/iron_verdict/static/js/connection.js` and the code that decides when it runs (overlay start on join and on login change, overlay stop on every leave path, session info on lookup). Additions elsewhere in the file (e.g. registering a new message type in `DISPATCH`) are not covered.
- VPortal calls in `src/iron_verdict/static/js/handlers.js` (overlay stop on session end and final join error)
- The VPortal login watch in `src/iron_verdict/static/js/screens/displayScreen.js` (restarts the display overlay when the login changes)
- `tests/js/connection.test.js` (overlay start/stop on every join/leave path)
- `tests/e2e/fake_vportal.py`
- `tests/e2e/test_vportal_integration.py`
- `tests/e2e/test_vportal_store.py`
- `tests/js/vportalStore.test.js`
- `tests/test_vportal_proxy.py`
- `docs/vportal-fake-server-fidelity.md`

A PR touches a protected file only if it changes VPortal behavior or the code paths named above; showing or hiding the VPortal corners in markup without changing when VPortal polls is not a VPortal change.

Rules:
- Every PR touching one of these files gets the label `vportal` and a checklist in the PR description of what to verify in the next manual test against the BVDK staging environment.
- The same checklist is merged into the standing issue #151 ("VPortal: Checkliste für den nächsten Staging-Test") when the PR is opened, so the maintainer has one list to work through at the next staging test. New points go under the matching section with the PR number. A point that already exists gets the PR number appended. Points the PR makes obsolete are removed. The PR is added to "Seit … ungetestet" under "Stand". If the PR is closed without merging, its points are removed again.
- The fake server (`tests/e2e/fake_vportal.py`) may only be changed with a justification recorded in `docs/vportal-fake-server-fidelity.md` (what real VPortal behavior it now mirrors, and how that is known) — never just "to make the test green".

## Workflow
- One issue per PR, one branch per issue. The PR description contains `Closes #<n>`.
- Never push directly to `main`. Merge only with green CI and approval by the maintainer.
- Issues and communication with the maintainer in German; code, commit messages, documentation and CHANGELOG stay in English.
- Open work is tracked in GitHub Issues (there is no backlog file).
- **Ask, don't assume.** When a decision belongs to the maintainer, ask before acting on it — never pick an answer from assumptions. This covers anything affecting product behavior, the critical path, VPortal, security, cost, external services, deployment, or scope (doing more or less than asked), and any rule that is ambiguous or contradicts the code.
  - Issues: if an issue has a "Zu klären" section or other open questions, get the answers before implementing the affected parts and record them in the issue so later sessions know them.
  - Propose the simplest version that meets the issue first; extras (movable/configurable blocks, extra input modes, clock-skew handling) only on the maintainer's request.
  - Backwards compatibility is only needed for what is released and in use (persisted sessions, stored layouts/codes of released features, the WebSocket protocol during a deploy). Unreleased features (see `[Unreleased]` in `CHANGELOG.md`) may change their stored formats freely.
  - Pure implementation details with an obvious convention in the codebase (naming, file placement, test structure) don't need a question — but state the choice in the PR so it can be reviewed.
- **Working an issue:** follow the skill `/work-on-issue <n>` (`.claude/skills/work-on-issue/SKILL.md`) — issue → clarification → branch → TDD → full test suite → docs → review → PR.
- **Independent review:** before opening a PR, run the read-only agent `live-reliability-reviewer` (`.claude/agents/live-reliability-reviewer.md`) on the diff and fix its blocking and should findings, or record in the PR why one does not apply. It checks the rules in this file (critical path, dropped messages, external dependencies, delays, VPortal, tests, docs) and whether the solution is proportionate to the issue; `[proportionality]` findings are implemented or declined with a reason in the PR description.

## Project Structure
- Place all application implementation files (code, modules, components) under /src directory.
- Place all application documentation files under /docs directory.
- Place all test files and test-related code under /tests directory.
- Place repository tooling scripts (CI/release helpers, not part of the app) under /scripts directory.

## GitHub
- Before committing any files, ask the user for confirmation if you're uncertain whether they should be committed, especially for generated files, logs, cache files, or system files.
- Never commit dependency directories, build artifacts, .env files, IDE configs, logs, or cache files; when in doubt about any file, ask before committing.

## Implementation
- Local sessions: use worktrees to implement new features or fixes; create them in the project folder under .worktrees
- Cloud sessions: a branch is sufficient, no worktree needed. Do not use the branch the session assigns (`ccr-…`); create `<type>/<n>-<slug>` from `origin/main` (e.g. `feat/53-reconnect-within-3s`) and push there — the maintainer permits this for every session.
- Branch names: `<type>/<n>-<slug>` — conventional-commit type, issue number, short kebab-case slug; no further `/` levels. Without an issue: `<type>/<slug>`.

## Changelog
- After completing a feature or fix, add one to three lines to the `[Unreleased]` section of `CHANGELOG.md` under the appropriate subsection (`Added`, `Fixed`, `Changed`, or `Removed`).
- Write from the perspective of someone deploying or using the app — describe observable behavior, not implementation details. No class names, method names, protocol internals, or technical mechanisms.
- Style: short, specific, no trailing period — match the tone of existing entries.

## Living documentation
- `docs/architecture.md` and `docs/testing.md` are living documents — after completing any feature, fix, or refactor, review them for staleness (same trigger as the CHANGELOG entry).
- Criterion: would a new contributor reading the doc afterwards build a correct mental model of how the system actually works? If a change shifts how the system or its tests are structured in a way the doc doesn't yet capture, update it.
- For `architecture.md`, this commonly means changes to (non-exhaustive): HTTP/WS endpoints, state managers, persistence, reconnection model, background tasks, scale flags, frontend module structure, external dependencies, configuration/env-var surface, authentication or security model, observability surface, deployment topology, or any architectural "Why:" rationale.
- For `testing.md`, this commonly means changes to (non-exhaustive): test categories, conventions, per-file purpose tables (backend or E2E), the regression suite, or known flakiness risks.
- If a change is architectural in a sense no existing section captures, add a new section or extend the most-related one — do not let it fall through because the doc had no slot for it.
- Match the existing tone — concise, structured, with "Why:" lines for load-bearing decisions. Edit tables and rationale in place rather than appending new sections; if a section becomes incoherent, rewrite it rather than patching.

## Testing
`docs/testing.md` is the source for how to run the tests, the test tiers, per-file tables and test conventions. The hard rules:
- Backend changes follow TDD — write a failing test first, then implement.
- Frontend-visible features get an E2E test of the user-visible flow in `tests/e2e/`.
- The regression gate `tests/e2e/test_competition_flow.py` is updated when a change affects the main flow (see `docs/testing.md`, "Regression gate").
- Before merging, the full suite is green — backend, Vitest and E2E.
- CI (`.github/workflows/ci.yml` and `image.yml`, described in `docs/testing.md`, "Continuous integration") must be green; branch protection on `main` requires its jobs. Never make CI green by skipping, disabling or retrying a test — fix it or document it in `docs/e2e-known-risks.md`.
- Cloud sessions get dependencies and Chromium from the environment's setup script (`docs/testing.md`, "Claude cloud environment setup").

## Security
- When adding or modifying features, always evaluate whether the change could introduce XSS, injection, or other OWASP Top 10 vulnerabilities.
- Flag any change that would render unsanitized user input as HTML.

## Plan Mode
- Make the plan extremely concise. Sacrifice grammar for the sake of concision.
- At the end of each plan, give me a list of unresolved questions to answer, if any.