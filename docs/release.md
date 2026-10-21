# Release, deploy and rollback

Runbook for the maintainer. The pipeline follows "build once, promote": the image that runs on Railway is bit-for-bit the image CI tested.

```
PR ──► image check (build + remote_safe E2E against the container, no push)
merge to main ──► Main workflow: CI + image check ──► GHCR sha-<commit>, main
   └─ only for a release commit (no tag v<pyproject version> yet):
      [approval Release-Kandidat] ──► Railway staging runs sha-<commit> ──► E2E (remote_safe) against staging
      ──► [approval Release] ──► tag vX.Y.Z + image vX.Y.Z (same digest) + GitHub release
Railway production ──► manual: Source Image tag set to vX.Y.Z
```

Image: `ghcr.io/abti247/iron_verdict`. Tags:

| Tag | Set by | Meaning |
|---|---|---|
| `sha-<7-char commit>` | Main workflow | Tested image of that commit on `main`. Never overwritten — a re-run of the Main workflow keeps the existing tag. |
| `main` | Main workflow | Same digest as the `sha-<commit>` of the latest tested commit on `main`. Not for production. |
| `vX.Y.Z` | Release workflow (end of the release chain) | Same digest as the `sha-<commit>` of the tagged commit, which passed staging. Production uses only these. |

Versions follow SemVer with a `v` prefix and no pre-release suffix (`v0.2.0`); the 0.x major already signals pre-1.0. Older releases up to `v0.1.4-beta` kept the `-beta` suffix.

The footer of the app shows `sha-<commit>` of the running image (baked in at build time; the release tag is only added later, so it cannot be baked in). If the Railway service sets an `APP_VERSION` variable, that overrides the baked value — remove it.

## One-time setup

- **Branch protection on `main`:** add `image` to the required status checks (next to `backend`, `js`, `e2e`).
- **GHCR write access for Actions:** the package `iron_verdict` already exists (pushed by hand so far), so GitHub → your profile → Packages → `iron_verdict` → Package settings → *Manage Actions access* → add the repository `abti247/iron_verdict` with role **Write**. Without it the Main and Release workflows fail at the push with `403`/`denied`. (A package first created by a workflow is linked automatically via the image's `org.opencontainers.image.source` label.)
- **Package visibility:** Railway pulls without credentials, so the package must stay **Public** (Package settings → Danger Zone → Change visibility). It is today, since Railway pulls `v0.1.4-beta`; check it once after the first workflow push. Alternative: keep it private and give Railway registry credentials.
- **Cloudflare (production):** Caching → Configuration → *Browser Cache TTL* = **Respect Existing Headers** (set 2026-10-18, #145). With the default (4 h) Cloudflare hands the app's static files to browsers as `max-age=14400` instead of `no-cache`, and a device that opened the app shortly before a deploy mixes new HTML with old JavaScript (black page). If a check below shows `max-age=…`: set the TTL back to *Respect Existing Headers*, then Caching → Configuration → **Purge Everything**, so no response stored with the old header remains.
- **Railway auto updates off:** under Settings → Source → Source Image → *Configure auto updates*, keep automatic updates disabled (production and staging). Deploys happen only when the tag reference is changed.

### Staging and approvals (set up 2026-10-16, #71)

- **Railway staging:** environment `staging` in the production project, same service, domain `https://ironverdict-staging.up.railway.app` (Railway subdomain, no Cloudflare), runs permanently, own `/data` volume. Variables as production, except `ALLOWED_ORIGIN=https://ironverdict-staging.up.railway.app`, `RATE_LIMIT_SESSION_CREATE=60/hour` and `RATE_LIMIT_SESSION_LOOKUP=120/minute`. No `APP_VERSION` variable — the release chain checks the footer for `sha-<commit>`.
- **Railway project token** of environment `staging` (Project Settings → Tokens). It may set the source image and deploy (checked 2026-10-16), and reaches nothing outside staging.
- **GitHub environments** (Settings → Environments), both with required reviewer `abti247` and deployment branches limited to `main`:
  - `Release-Kandidat` — secret `RAILWAY_TOKEN` (the project token). Approving it deploys to staging.
  - `Release` — no secrets. Approving it tags and releases.
- **Repository variables** (Settings → Secrets and variables → Actions → Variables): `RAILWAY_SERVICE_ID`, `RAILWAY_ENVIRONMENT_ID` (staging). Not secret.
- The tag is created by the workflow (`GITHUB_TOKEN`, `contents: write`). A tag ruleset that restricts creating `v*` tags must allow GitHub Actions.

## Release

Run `/release` in a Claude session; it does steps 1–2 with you. By hand:

1. Check that the **Main** workflow of the current head of `main` is green.
2. On a branch: move `[Unreleased]` in `CHANGELOG.md` into `## [X.Y.Z] - YYYY-MM-DD`, add the compare link `[X.Y.Z]: https://github.com/abti247/iron_verdict/compare/v<previous>...vX.Y.Z` at the end of the section, leave an empty `[Unreleased]` with its four subsections, set `version = "X.Y.Z"` in `pyproject.toml`. PR, merge.
   - Guide screenshots: if the judge screen, the display result, the reasons or the layout editor look different since the last release, run `python scripts/guide_screenshots.py` and commit the changed images in this PR (see `docs/testing.md`, Guide screenshots).
3. The **Main** workflow of the merge commit runs CI, the image check and publishes `sha-<commit>`. Job `release-check` then sees that `vX.Y.Z` does not exist yet and the commit is the head of `main`, checks the version format and the CHANGELOG section, and the run stops at **approval Release-Kandidat** (Actions → the run → *Review deployments*). For every other push (`pyproject.toml` version already tagged) `staging` and `release` are skipped and the run is green.
   - If `main` moved on before the run reached `release-check`, the release is left to the newer commit's run (its version is still untagged).
4. **Approve Release-Kandidat.** Job `staging` (never two at once: concurrency group `railway-staging`; while one runs, only the newest waiting run is kept, an older waiting one is cancelled) points Railway staging at `sha-<commit>` and deploys it (`scripts/railway_deploy.sh`), waits until Railway reports this deployment as successful, `/health` answers and the footer shows `sha-<commit>` (at most 10 minutes), then runs the `remote_safe` E2E tests against staging. Staging keeps running this version afterwards.
   - **Red:** no tag, no image tag, no release. Traces: artifact `playwright-traces-staging`. Railway outage or similar → fix it, then *Re-run failed jobs* (asks for the approval again; same commit). Code defect → fix it with a normal PR, then a new release PR with a new version (the failed version is never tagged; its CHANGELOG section moves into the new one). Until that release PR is merged, `vX.Y.Z` is still untagged, so every push to `main` stops at approval Release-Kandidat again — reject those approvals (each rejected run shows red; that red is not a failure of the commit).
5. **Approve Release.** `release.yml` checks the version against `pyproject.toml`, re-tags `sha-<commit>` as `vX.Y.Z` with [scripts/retag_image.sh](../scripts/retag_image.sh) (copies the manifest unchanged, so the digest stays identical) and compares the digests, creates the annotated tag `vX.Y.Z` on the commit, and creates the GitHub release with the CHANGELOG section and the `docker pull` line. The job summary shows both digests. A re-run after a failure here is safe (same digest; a tag already on this commit is kept). A tag already on another commit stops the job before the image is re-tagged, so a second run of the same version cannot move `vX.Y.Z`.
   - Rejecting this approval leaves no tag; *Re-run failed jobs* asks again.

Pushing a `v*` tag by hand starts nothing: no release bypasses staging.

## Deploy (Railway)

1. Railway → service `iron_verdict` → **Settings → Source → Source Image** → edit (pencil).
2. Change the tag of `ghcr.io/abti247/iron_verdict:<old>` to the new `vX.Y.Z`, save.
3. Deploy the change (if Railway stages it as a pending change, apply/deploy it). Wait until the new deployment is *Active*.
4. Check: `https://iron-verdict.com/health` answers `{"status":"ok"}`, the landing page footer shows the `sha-<commit>` of the release (job summary of the Release workflow), create a test session and join as a judge, and `/static/js/app.js` answers `cache-control: no-cache` (browser network tab → `app.js` → Response headers, or `curl -sI`). The deploy log shows `allowed_origin_configured` with `https://iron-verdict.com`; a missing `ALLOWED_ORIGIN` makes the deployment fail with `allowed_origin_missing`.

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
- [ ] Once, for the first competition on a release after v0.2.1: hard-reload every judge and display device (Ctrl+Shift+R, or clear the site data on phones). Static files are revalidated on every load since then (#135, #145); devices may still hold older files the browser considers fresh.
- [ ] `https://iron-verdict.com/static/js/app.js` answers `cache-control: no-cache` (network tab or `curl -sI`; if it shows `max-age=…`, fix Cloudflare as described under One-time setup).
- [ ] `/health` ok; a test session works end to end: 3 judges + display, vote, result, Next Lift, reload of a judge.
- [ ] For VPortal competitions: `/vportal` session connects to the federation and shows the current lifter on the display.
- [ ] Fallback known: the app can run locally on a laptop on the venue Wi-Fi (README, "Running locally on competition WiFi").
