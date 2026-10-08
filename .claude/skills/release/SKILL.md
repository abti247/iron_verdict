---
name: release
description: 'Cut a release of Iron Verdict: turn CHANGELOG [Unreleased] into a version section, bump pyproject.toml, merge, tag vX.Y.Z so the Release workflow promotes the tested image, then hand the maintainer the Railway deploy and rollback steps. Use when asked to release, "Release erstellen" or `/release 0.2.0`.'
argument-hint: <version, e.g. 0.2.0>
---

# Release $ARGUMENTS

`.claude/CLAUDE.md` and [docs/release.md](../../../docs/release.md) are the rule sources; this skill walks through the runbook. Talk to the maintainer in **German**; CHANGELOG, commit messages and code stay in **English**.

A release never builds anything: it promotes the image the Main workflow already tested (`sha-<commit>`) to `vX.Y.Z`. Deploying to Railway stays a manual step of the maintainer.

## 1. Decide the version

- Format: SemVer with `v` prefix, **no** pre-release suffix (`v0.2.0`). Check the latest tag (`git ls-remote --tags origin 'v*'`) and the `[Unreleased]` entries; propose the next version (new features → minor, only fixes → patch while in 0.x) and **ask the maintainer to confirm**. If `$ARGUMENTS` is given, still confirm it.
- `[Unreleased]` must have at least one entry. If it is empty, stop: there is nothing to release.

## 2. Release PR

On the session branch (cloud) or a new branch `release/vX.Y.Z` from up-to-date `origin/main`:

- `CHANGELOG.md`:
  - Rename the `[Unreleased]` content to `## [X.Y.Z] - <today, YYYY-MM-DD>`; drop subsections without entries.
  - End the section with the compare link `[X.Y.Z]: https://github.com/abti247/iron_verdict/compare/v<previous>...vX.Y.Z` (same style as the older sections).
  - Above it, add a fresh `## [Unreleased]` with empty `### Added`, `### Changed`, `### Fixed`, `### Removed`.
- `pyproject.toml`: `version = "X.Y.Z"` (the Release workflow refuses a tag that does not match).
- Check: `python scripts/changelog_section.py X.Y.Z` prints the section; `pytest tests/test_changelog_section.py`.
- Commit (`chore(release): vX.Y.Z`), push, open the PR (German prose, no `Closes`). Show the maintainer the release notes preview.
- The maintainer merges after green CI. Do not merge yourself.

## 3. Wait for the tested image

After the merge, the **Main** workflow for the merge commit must be green — it pushes `ghcr.io/abti247/iron_verdict:sha-<7-char commit>`. Check its run (Actions tab / GitHub tools) and tell the maintainer if it fails; never tag a commit whose Main run is not green.

## 4. Tag

Confirm with the maintainer, then:

```bash
git fetch origin main
git log -1 --oneline origin/main     # must be the release merge commit
git tag -a vX.Y.Z origin/main -m "vX.Y.Z"
git push origin vX.Y.Z
```

If pushing tags is not possible from this session, give the maintainer these commands instead.

## 5. Check the Release workflow

- The **Release** workflow must be green. Its job summary shows the digests of `sha-<commit>` and `vX.Y.Z` — they must be identical.
- GitHub → Releases shows `vX.Y.Z` with the CHANGELOG section and `docker pull ghcr.io/abti247/iron_verdict:vX.Y.Z`.
- On "`sha-<commit>` not found": the Main run was not finished — re-run the Release job once it is green. Do not move or recreate the tag.

(After #71: instead of pushing the tag yourself, trigger the staging workflow, which sets the tag after green E2E tests on Railway staging.)

## 6. Hand over deploy and rollback

Tell the maintainer, in German, with the concrete values filled in:

- **Deploy:** Railway → service `iron_verdict` → Settings → Source → Source Image → tag from `v<previous>` to `vX.Y.Z` → save and deploy. Then check `/health`, the footer shows `sha-<commit>`, a test session works.
- **Rollback:** same place, tag back to `v<previous>`, deploy. About one minute, no build.
- Not on a competition day unless it is a rollback; checklist in `docs/release.md`.
