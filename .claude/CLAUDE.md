# Project Overview

**Iron Verdict** - a web app for powerlifting competition judging.

The goal of the app is to provide an easy access to a tool for powerlifting judging.

## Project Structure
- Place all application implementation files (code, modules, components) under /src directory.
- Place all application documentation files under /docs directory.
- Place all test files and test-related code under /tests directory.

## GitHub
- Before committing any files, ask the user for confirmation if you're uncertain whether they should be committed, especially for generated files, logs, cache files, or system files.
- Never commit dependency directories, build artifacts, .env files, IDE configs, logs, or cache files; when in doubt about any file, ask before committing.

## Implementation
- Use worktrees to implement new features or fixes
- Create worktrees in the project folder under .worktrees

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

### Structure
- Backend tests (unit + integration) live in `tests/` — run with `pytest tests/ --ignore=tests/e2e`
- E2E tests live in `tests/e2e/` — run with `pytest tests/e2e/`
- Run all tests: `pytest`

### When to write tests
- Backend changes: follow TDD — write a failing test first, then implement
- Frontend-visible features: add an E2E test in `tests/e2e/`

### Test categories
- **Backend unit tests**: test individual modules directly (e.g., SessionManager, ConnectionManager)
- **Backend integration tests**: test HTTP/WebSocket endpoints via FastAPI TestClient
- **E2E feature tests**: Playwright tests targeting specific features (e.g., double-vote prevention, reconnection)
- **E2E regression suite**: `tests/e2e/test_competition_flow.py` — comprehensive end-to-end walkthrough of a full competition; acts as the primary regression gate to catch cross-feature breakage

### Regression strategy
- `test_competition_flow.py` must exercise the full happy-path lifecycle (create session → judges join → vote → display updates → next attempt → end session) and be updated when new features affect the main flow
- Feature-specific E2E tests cover edge cases and niche behavior
- Before merging, run the full test suite — both backend and E2E

### Reporting
- Use `pytest --tb=short -v` for human-readable pass/fail output
- Backend tests: rely on descriptive function names (no docstrings needed)
- E2E tests: add a docstring explaining the scenario, since multi-step flows aren't obvious from the name alone

## Security
- When adding or modifying features, always evaluate whether the change could introduce XSS, injection, or other OWASP Top 10 vulnerabilities.
- Flag any change that would render unsanitized user input as HTML.

## Plan Mode
- Make the plan extremely concise. Sacrifice grammar for the sake of concision.
- At the end of each plan, give me a list of unresolved questions to answer, if any.