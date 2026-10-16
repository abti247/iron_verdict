---
name: release
description: 'Cut a release of Iron Verdict: turn CHANGELOG [Unreleased] into a version section, bump pyproject.toml, open the release PR, then guide the maintainer through the two approvals of the release chain (Railway staging E2E, then tag + release) and the Railway deploy and rollback. Use when asked to release, "Release erstellen" or `/release 0.2.0`.'
argument-hint: <version, e.g. 0.2.0>
---

# Release $ARGUMENTS

`.claude/CLAUDE.md` and [docs/release.md](../../../docs/release.md) are the rule sources; this skill walks through the runbook. Talk to the maintainer in **German**; CHANGELOG, commit messages and code stay in **English**.

A release never builds anything: it promotes the image the Main workflow already tested (`sha-<commit>`) to `vX.Y.Z`, after it passed the E2E tests on Railway staging. The session never pushes a tag — the release chain in `main.yml` creates it after the maintainer's second approval. Deploying to production stays a manual step of the maintainer.

## 1. Decide the version

- Format: SemVer with `v` prefix, **no** pre-release suffix (`v0.2.0`). Check the latest tag (`git ls-remote --tags origin 'v*'`) and the `[Unreleased]` entries; propose the next version (new features → minor, only fixes → patch while in 0.x) and **ask the maintainer to confirm**. If `$ARGUMENTS` is given, still confirm it.
- `[Unreleased]` must have at least one entry. If it is empty, stop: there is nothing to release.

## 2. Release PR

On the session branch (cloud) or a new branch `release/vX.Y.Z` from up-to-date `origin/main`:

- `CHANGELOG.md`:
  - Rename the `[Unreleased]` content to `## [X.Y.Z] - <today, YYYY-MM-DD>`; drop subsections without entries.
  - End the section with the compare link `[X.Y.Z]: https://github.com/abti247/iron_verdict/compare/v<previous>...vX.Y.Z` (same style as the older sections).
  - Above it, add a fresh `## [Unreleased]` with empty `### Added`, `### Changed`, `### Fixed`, `### Removed`.
- `pyproject.toml`: `version = "X.Y.Z"` — merging a commit with a not yet tagged version is what starts the release chain.
- Check: `python scripts/changelog_section.py X.Y.Z` prints the section; `pytest tests/test_changelog_section.py`.
- Commit (`chore(release): vX.Y.Z`), push, open the PR (German prose, no `Closes`). Show the maintainer the release notes preview.
- The maintainer merges after green CI. Do not merge yourself.

## 3. Release chain: two approvals by the maintainer

After the merge, the **Main** workflow of the merge commit runs CI and the image check, publishes `ghcr.io/abti247/iron_verdict:sha-<7-char commit>` and stops at **approval Release-Kandidat** (job `staging`). Tell the maintainer, in German, with the link to the run:

1. **Release-Kandidat freigeben** (run → *Review deployments*): deploys `sha-<commit>` to Railway staging (`https://ironverdict-staging.up.railway.app`) and runs the `remote_safe` E2E tests against it.
2. Only if `staging` is green: **Release freigeben**. `release.yml` re-tags the image as `vX.Y.Z` (same digest), creates the tag `vX.Y.Z` and the GitHub release.

Check the run (GitHub tools) and report:

- `release-check` skipped the chain (`vX.Y.Z` already exists, or `main` moved on): say so; with a newer head, its run carries the release.
- `staging` red: no tag, no release. Read the failing step and the `playwright-traces-staging` artifact. Railway outage → the maintainer fixes it and uses *Re-run failed jobs*. Code defect → a normal fix PR, then a new release PR with a new version (step 1). Never retry a failing test until it passes.
- `release` green: its job summary shows the digests of `sha-<commit>` and `vX.Y.Z` — identical. GitHub → Releases shows `vX.Y.Z` with the CHANGELOG section and `docker pull ghcr.io/abti247/iron_verdict:vX.Y.Z`.

Do not push a tag yourself: a pushed tag starts nothing, and the chain would then skip the release because the tag exists.

## 4. Hand over deploy and rollback

Tell the maintainer, in German, with the concrete values filled in:

- **Deploy:** Railway → service `iron_verdict` → Settings → Source → Source Image → tag from `v<previous>` to `vX.Y.Z` → save and deploy. Then check `/health`, the footer shows `sha-<commit>`, a test session works.
- **Rollback:** same place, tag back to `v<previous>`, deploy. About one minute, no build.
- Not on a competition day unless it is a rollback; checklist in `docs/release.md`.
