---
name: work-on-issue
description: 'Work a GitHub issue of abti247/iron_verdict from reading it to an open PR — clarify open questions, branch, TDD, full test suite, CHANGELOG and living docs, independent review by the live-reliability-reviewer agent, PR with "Closes #<n>". Use when asked to work on, implement or "bearbeiten" an issue, e.g. `/work-on-issue 48`.'
argument-hint: <issue-number>
---

# Work on issue #$ARGUMENTS

Follow these steps in order. `.claude/CLAUDE.md` is the rule source; if it contradicts this skill, CLAUDE.md wins — and say so to the maintainer.

Communicate with the maintainer (chat, issue comments, PR description prose) in **German**. Code, commit messages, docs and CHANGELOG stay in **English**.

## 1. Read the issue

In cloud sessions GitHub GraphQL is blocked, so `gh issue view` fails. Use the REST API:

```bash
gh api repos/abti247/iron_verdict/issues/$ARGUMENTS
gh api repos/abti247/iron_verdict/issues/$ARGUMENTS/comments
```

(The `mcp__github__issue_read` tool works too, if available.) Read the body **and all comments** — answers to earlier questions live there. Note dependencies ("Nach #…", "Abhängigkeiten") and check that they are closed/merged; if not, tell the maintainer before starting. Line references in issues are tied to a commit — re-check them against the current code.

## 2. Clarify, then confirm a plan

- Collect everything open: a "Zu klären" section, open questions, ambiguous acceptance criteria, and any decision CLAUDE.md reserves for the maintainer (product behavior, critical path, VPortal, security, cost, external services, deployment, scope).
- Ask those questions **before** implementing the affected parts (use AskUserQuestion when available). Never pick an answer from assumptions.
- Record the answers as a comment on the issue (`gh api repos/abti247/iron_verdict/issues/$ARGUMENTS/comments -f body=...`) so later sessions know them.
- Give a short plan (files to touch, tests to add, docs to update) and wait for confirmation. Pure implementation details with an obvious codebase convention need no question — list them in the PR instead.

## 3. Branch

One issue per branch, never work on `main`.
- Cloud session: use the branch the session assigns; otherwise create one from up-to-date `origin/main` (`git fetch origin main && git checkout -b <type>/<n>-<slug> origin/main`).
- Local session: create a worktree under `.worktrees/`.

## 4. Test first, then implement (TDD)

- Backend change: write a failing test in `tests/` first, run it, see it fail for the right reason, then implement.
- Frontend-visible change: add or extend an E2E test in `tests/e2e/` (with a docstring describing the scenario).
- Critical-path change (anything after a judge/display joined: voting, timer, results, reconnection, reload): an E2E test is mandatory; network-related changes also need a connection-loss scenario (drop, reconnect, reload).
- Main-flow change: update `tests/e2e/test_competition_flow.py`.
- Respect the critical-path rules (no external runtime dependencies, no silently dropped messages, no unjustified delays) and `src/iron_verdict/static/AGENTS.md` for frontend structure.
- VPortal files: changes to `tests/e2e/fake_vportal.py` only with a justification in `docs/vportal-fake-server-fidelity.md`.

Commit in small, descriptive steps (English messages).

## 5. Run the full test suite

```bash
pytest tests/ --ignore=tests/e2e --tb=short -v
pytest tests/e2e/ --tb=short -v
npm test   # only if JS modules under test changed or package.json exists with vitest
```

All green before continuing. Keep the summary (passed/failed counts) for the PR. If something fails that is unrelated to the change, verify it also fails on `origin/main` and report it — never skip or disable a test.

## 6. CHANGELOG and living docs

- `CHANGELOG.md`: one to three lines under `[Unreleased]` (`Added`/`Changed`/`Fixed`/`Removed`), user perspective, no implementation details, no trailing period. Skip only for changes with no user/deployer-visible effect, and say so in the PR.
- Review `docs/architecture.md` and `docs/testing.md` for staleness and update them in place.

## 7. Independent review

Launch the `live-reliability-reviewer` agent (Agent tool, `subagent_type: live-reliability-reviewer`) on the branch diff against `origin/main`, giving it the issue number. Fix every **blocking** and **should** finding, or record in the PR why one does not apply. Re-run the reviewer after substantial fixes, and re-run the affected tests.

## 8. Open the PR

Push the branch (`git push -u origin <branch>`), then open the PR against `main`:

- Title: conventional-commit style in English (e.g. `fix(judge): ...`).
- Body (German prose; file names and code in English):
  - `Closes #$ARGUMENTS`
  - What changed and why, plus implementation choices made without asking (see step 2)
  - **Testnachweis**: commands run and pass/fail counts, new tests named
  - Reviewer result: findings and how each was handled
  - If VPortal files were touched: add the `vportal` label and a checklist of what to verify in the next manual test against the BVDK staging environment (start from the reviewer's checklist)
- Do not merge — merging needs green CI and the maintainer's approval.

Finally, tell the maintainer the PR link and anything still open.
