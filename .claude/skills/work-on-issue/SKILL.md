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

One issue per branch, never work on `main`. Name and base: `.claude/CLAUDE.md`, "Implementation".
- Cloud session: `git fetch origin main && git checkout -b <type>/<n>-<slug> origin/main`, push there.
- Local session: create a worktree under `.worktrees/` on a branch with that name.

## 4. Test first, then implement (TDD)

Test rules: `.claude/CLAUDE.md`, "Critical Path" and "Testing"; conventions (cheapest level, docstrings, selectors): `docs/testing.md`, "Conventions". Also respect `.claude/CLAUDE.md`, "VPortal Protection", and `src/iron_verdict/static/AGENTS.md` for frontend structure.

1. Decide which tests the change needs and at which level.
2. Write them first, run them, and see them fail for the right reason.
3. Implement until they pass.

Commit in small, descriptive steps (English messages).

## 5. Run the full test suite

```bash
pytest tests/ --ignore=tests/e2e --tb=short -v
pytest tests/e2e/ --tb=short -v
npm test
```

All green before continuing. Keep the summary (passed/failed counts) for the PR. If something fails that is unrelated to the change, verify it also fails on `origin/main` and report it (see `.claude/CLAUDE.md`, "Testing", for what never to do about a failing test).

## 6. CHANGELOG and living docs

- `CHANGELOG.md`: add the entry per `.claude/CLAUDE.md`, "Changelog". Skip only for changes with no user/deployer-visible effect, and say so in the PR.
- Review `docs/architecture.md` and `docs/testing.md` per `.claude/CLAUDE.md`, "Living documentation".

## 7. Independent review

Launch the `live-reliability-reviewer` agent (Agent tool, `subagent_type: live-reliability-reviewer`) on the branch diff against `origin/main`, giving it the issue number. Handle its findings per `.claude/CLAUDE.md`, "Workflow" (Independent review). A blocking or should finding that does not apply gets the reason recorded in the PR. Re-run the reviewer after substantial fixes, and re-run the affected tests.

## 8. Open the PR

Push the branch (`git push -u origin <branch>`), then open the PR against `main`:

- Title: conventional-commit style in English (e.g. `fix(judge): ...`).
- Body (German prose; file names and code in English):
  - `Closes #$ARGUMENTS`
  - What changed and why, plus implementation choices made without asking (see step 2)
  - **Testnachweis**: commands run and pass/fail counts, new tests named
  - Reviewer result: findings and how each was handled — answer every `[proportionality]` finding explicitly (implemented, or declined with the reason)
  - If VPortal files were touched: the label and staging checklist that `.claude/CLAUDE.md`, "VPortal Protection", requires (start from the reviewer's checklist)
- If VPortal files were touched: after opening the PR, merge its checklist into issue #151 as that section describes. Read the current body, edit it and write it back: `gh api repos/abti247/iron_verdict/issues/151 -X PATCH -F body=@<file>`.
- Do not merge — merging needs green CI and the maintainer's approval.

Finally, tell the maintainer the PR link and anything still open.
