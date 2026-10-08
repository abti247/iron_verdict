# Release, deploy and rollback

Runbook for the maintainer. The pipeline follows "build once, promote": the image that runs on Railway is bit-for-bit the image CI tested.

```
PR ──► image check (build + container smoke test, no push)
merge to main ──► Main workflow: CI + image check ──► GHCR sha-<commit>, main
tag vX.Y.Z ──► Release workflow: sha-<commit> re-tagged as vX.Y.Z (no rebuild) + GitHub release
Railway ──► manual: Source Image tag set to vX.Y.Z
```

Image: `ghcr.io/abti247/iron_verdict`. Tags:

| Tag | Set by | Meaning |
|---|---|---|
| `sha-<7-char commit>` | Main workflow | Tested image of that commit on `main`. Never overwritten. |
| `main` | Main workflow | Latest tested commit on `main`. Not for production. |
| `vX.Y.Z` | Release workflow | Same digest as the `sha-<commit>` of the tagged commit. Production uses only these. |

Versions follow SemVer with a `v` prefix and no pre-release suffix (`v0.2.0`); the 0.x major already signals pre-1.0. Older releases up to `v0.1.4-beta` kept the `-beta` suffix.

The footer of the app shows `sha-<commit>` of the running image (baked in at build time; the release tag is only added later, so it cannot be baked in). If the Railway service sets an `APP_VERSION` variable, that overrides the baked value — remove it.

## One-time setup

- **Branch protection on `main`:** add `image` to the required status checks (next to `backend`, `js`, `e2e`).
- **GHCR write access for Actions:** GitHub → Packages → `iron_verdict` → Package settings → *Manage Actions access* → add the repository `abti247/iron_verdict` with role **Write**. Without it the Main and Release workflows fail at the push with `403`/`denied`. The image's `org.opencontainers.image.source` label links new pushes to the repository.
- **Railway auto updates off:** under Settings → Source → Source Image → *Configure auto updates*, keep automatic updates disabled. Deploys happen only when the tag reference is changed.

## Release

Run `/release` in a Claude session; it does the following steps with you. By hand:

1. Check that the **Main** workflow for the commit to release (normally the head of `main`) is green — it published `sha-<commit>`.
2. On a branch: move `[Unreleased]` in `CHANGELOG.md` into `## [X.Y.Z] - YYYY-MM-DD`, add the compare link `[X.Y.Z]: https://github.com/abti247/iron_verdict/compare/v<previous>...vX.Y.Z` at the end of the section, leave an empty `[Unreleased]` with its four subsections, set `version = "X.Y.Z"` in `pyproject.toml`. PR, merge, wait for the Main workflow to turn green.
3. Tag the merge commit and push the tag:
   ```bash
   git fetch origin main
   git tag -a vX.Y.Z origin/main -m "vX.Y.Z"
   git push origin vX.Y.Z
   ```
4. The **Release** workflow checks the tag format, that `pyproject.toml` has the same version and that the commit is on `main`; re-tags `sha-<commit>` as `vX.Y.Z` and compares the digests; creates the GitHub release with the CHANGELOG section and the `docker pull` line. The job summary shows both digests.
   - *`sha-<commit>` not found*: the Main workflow for that commit is not finished or failed. Wait for it to be green, then **Re-run** the Release job — do not move the tag.

## Deploy (Railway)

1. Railway → service `iron_verdict` → **Settings → Source → Source Image** → edit (pencil).
2. Change the tag of `ghcr.io/abti247/iron_verdict:<old>` to the new `vX.Y.Z`, save.
3. Deploy the change (if Railway stages it as a pending change, apply/deploy it). Wait until the new deployment is *Active*.
4. Check: `https://iron-verdict.com/health` answers `{"status":"ok"}`, the landing page footer shows the `sha-<commit>` of the release (job summary of the Release workflow), create a test session and join as a judge.

The `/data` volume and all variables stay attached; active sessions survive via the snapshot written on shutdown.

## Rollback

Same as a deploy, with the **previous** version tag (the one before the faulty release, listed under GitHub → Releases). Takes about a minute: no build involved, the old image is still in GHCR.

1. Railway → Settings → Source → Source Image → set the tag back to `v<previous>`, save, deploy.
2. Check `/health` and the footer version as above.
3. Open an issue for the faulty release. Do not delete its tag or image — it is the evidence.

## Checklist before a competition

- [ ] Production runs a release tag (`vX.Y.Z`, not `main` or `sha-…`); footer version matches that release.
- [ ] The previous release tag is noted (rollback target) and still listed under GitHub → Releases.
- [ ] No deploy planned during the competition.
- [ ] `/health` ok; a test session works end to end: 3 judges + display, vote, result, Next Lift, reload of a judge.
- [ ] For VPortal competitions: `/vportal` session connects to the federation and shows the current lifter on the display.
- [ ] Fallback known: the app can run locally on a laptop on the venue Wi-Fi (README, "Running locally on competition WiFi").
