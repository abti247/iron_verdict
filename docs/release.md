# Release, deploy and rollback

Runbook for the maintainer. The pipeline follows "build once, promote": the image that runs on Railway is bit-for-bit the image CI tested.

```
PR ──► image check (build + remote_safe E2E against the container, no push)
merge to main ──► Main workflow: CI + image check ──► GHCR sha-<commit>, main
   └─ only for a release commit (no tag v<pyproject version> yet):
      [approval Release-Kandidat] ──► Railway staging runs sha-<commit> ──► E2E (remote_safe) against staging
      ──► [approval Release] ──► tag vX.Y.Z + image vX.Y.Z (same digest) + GitHub release
      ──► [approval Produktion] ──► Railway production runs vX.Y.Z ──► E2E (prod_safe) against iron-verdict.com
Rollback ──► manual: Source Image tag set back to v<previous>
```

Image: `ghcr.io/abti247/iron_verdict`. Tags:

| Tag | Set by | Meaning |
|---|---|---|
| `sha-<7-char commit>` | Main workflow | Tested image of that commit on `main`. Never overwritten — a re-run of the Main workflow keeps the existing tag. |
| `main` | Main workflow | Same digest as the `sha-<commit>` of the latest tested commit on `main`. Not for production. |
| `vX.Y.Z` | Release workflow (release chain) | Same digest as the `sha-<commit>` of the tagged commit, which passed staging. Production uses only these. |

Versions follow SemVer with a `v` prefix and no pre-release suffix (`v0.2.0`); the 0.x major already signals pre-1.0. Older releases up to `v0.1.4-beta` kept the `-beta` suffix.

The footer of the app shows `sha-<commit>` of the running image (baked in at build time; the release tag is only added later, so it cannot be baked in). If the Railway service sets an `APP_VERSION` variable, that overrides the baked value — remove it.

## One-time setup

- **Branch protection on `main`:** add `image` to the required status checks (next to `backend`, `js`, `e2e`).
- **GHCR write access for Actions:** the package `iron_verdict` already exists (pushed by hand so far), so GitHub → your profile → Packages → `iron_verdict` → Package settings → *Manage Actions access* → add the repository `abti247/iron_verdict` with role **Write**. Without it the Main and Release workflows fail at the push with `403`/`denied`. (A package first created by a workflow is linked automatically via the image's `org.opencontainers.image.source` label.)
- **Package visibility:** Railway pulls without credentials, so the package must stay **Public** (Package settings → Danger Zone → Change visibility). It is today, since Railway pulls `v0.1.4-beta`; check it once after the first workflow push. Alternative: keep it private and give Railway registry credentials.
- **Cloudflare (production):** Caching → Configuration → *Browser Cache TTL* = **Respect Existing Headers** (set 2026-10-18, #145). With the default (4 h) Cloudflare hands the app's static files to browsers as `max-age=14400` instead of `no-cache`, and a device that opened the app shortly before a deploy mixes new HTML with old JavaScript (black page). If a check below shows `max-age=…`: set the TTL back to *Respect Existing Headers*, then Caching → Configuration → **Purge Everything**, so no response stored with the old header remains.
- **Railway auto updates off:** under Settings → Source → Source Image → *Configure auto updates*, keep automatic updates disabled (production and staging). Deploys happen only when the release chain (or a manual rollback) changes the tag reference.

### Staging and approvals (set up 2026-10-16, #71)

- **Railway staging:** environment `staging` in the production project, same service, domain `https://ironverdict-staging.up.railway.app` (Railway subdomain, no Cloudflare), runs permanently, own `/data` volume. Variables as production, except `ALLOWED_ORIGIN=https://ironverdict-staging.up.railway.app`, `RATE_LIMIT_SESSION_CREATE=60/hour` and `RATE_LIMIT_SESSION_LOOKUP=120/minute`. No `APP_VERSION` variable — the release chain checks the footer for `sha-<commit>`.
- **Railway project token** of environment `staging` (Project Settings → Tokens). It may set the source image and deploy (checked 2026-10-16), and reaches nothing outside staging. Railway can invalidate it: on 2026-10-29 the `staging` job failed at its first call with `Railway API: Not Authorized` (`serviceInstanceUpdate`), and Project Settings → Tokens showed "Token invalid, please issue a new token". Then create a new token for environment `staging`, replace the secret `RAILWAY_TOKEN` in the GitHub environment `Release-Kandidat`, delete the invalid token and *Re-run failed jobs*.
- **GitHub environments** (Settings → Environments), all with required reviewer `abti247` and deployment branches limited to `main`:
  - `Release-Kandidat` — secret `RAILWAY_TOKEN` (the staging project token). Approving it deploys to staging.
  - `Release` — no secrets. Approving it tags and releases.
  - `Produktion` — secret `RAILWAY_PROD_TOKEN` (the production project token, see below). Approving it deploys to production.
- **Repository variables** (Settings → Secrets and variables → Actions → Variables): `RAILWAY_SERVICE_ID` (the service, same in both environments), `RAILWAY_ENVIRONMENT_ID` (staging), `RAILWAY_PROD_ENVIRONMENT_ID` (production). Not secret.
- The tag is created by the workflow (`GITHUB_TOKEN`, `contents: write`). A tag ruleset that restricts creating `v*` tags must allow GitHub Actions.

### Production deploy (#140)

- **Railway project token** of environment `production` (Project Settings → Tokens), stored only as secret `RAILWAY_PROD_TOKEN` in the GitHub environment `Produktion`. The staging token stays limited to staging. Like the staging token, Railway can invalidate it: the `production` job then fails at its first call with `Railway API: Not Authorized`, and production keeps running the previous version. Create a new token for environment `production`, replace the secret, delete the invalid token and *Re-run failed jobs*.
- **Environment ID** of production (Railway → environment `production` → Settings, or the URL `…/environment/<id>`) as repository variable `RAILWAY_PROD_ENVIRONMENT_ID`.
- **Cloudflare:** the production check comes from GitHub runners (data-center IPs) through Cloudflare with Bot Fight Mode on. The trial run from a Claude cloud IP was not challenged (#131); if Cloudflare blocks the runners (job `production-check` red with `403` or a challenge page in the trace), production itself is fine — decide on an exception then (#140).

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
6. **Approve Produktion** — only when no competition is running or about to start on production (checklist below; e.g. Grafana dashboard: no active sessions, no competition announced). The deploy restarts the container and every judge and display reconnects. This approval is independent of *Release* and may stay open for days (GitHub fails it after 30 days; then *Re-run failed jobs*). Job `production` (concurrency group `railway-production`) points Railway production at `vX.Y.Z` and deploys it (`scripts/railway_deploy.sh`), waits until Railway reports this deployment as successful, `/health` answers on `https://iron-verdict.com` and the footer shows `sha-<commit>` (at most 10 minutes). Job `production-check` then runs the `prod_safe` E2E tests (`test_smoke.py`, `test_competition_flow.py`, about 7 sessions, about 3 minutes) against `https://iron-verdict.com`; every test ends its sessions afterwards, so none stays in the snapshot.
   - **`production` red:** production keeps running the previous version (Railway only switches to a successful deployment), unless the footer check timed out after a successful deployment — then check the footer by hand. Token invalid → see One-time setup; Railway outage → *Re-run failed jobs* (asks for the approval again).
   - **`production-check` red:** production runs the new version; nothing is rolled back automatically. Look at the failing test and the `playwright-traces-production` artifact: a real defect → [Rollback](#rollback) now, then an issue. A Railway/network hiccup → *Re-run failed jobs* repeats only the tests (no new deploy, no new approval; mind the 10 sessions/hour/IP limit). Never retry a failing test until it passes.
   - **Green:** still check by hand once that `/static/js/app.js` answers `cache-control: no-cache` (Cloudflare, see One-time setup); the deploy log shows `allowed_origin_configured` with `https://iron-verdict.com` and `metrics_enabled` ([monitoring.md](monitoring.md)).
   - Rejecting this approval leaves production on the previous version; the release (tag, image, GitHub release) stays.

Pushing a `v*` tag by hand starts nothing: no release bypasses staging.

## Deploy (Railway)

The release chain deploys production (step 6 above); the `/data` volume and all variables stay attached, and active sessions survive via the snapshot written on shutdown. A missing `ALLOWED_ORIGIN` makes the deployment fail with `allowed_origin_missing`; `metrics_disabled` in the deploy log means Grafana gets no metrics ([monitoring.md](monitoring.md)).

After the deploy the Grafana uptime check keeps watching `/health` ([docs/monitoring.md](monitoring.md)); Railway itself checks it only during the deploy.

## Rollback

Manual, in Railway, with the **previous** version tag (the one before the faulty release, listed under GitHub → Releases). Takes about a minute: no build involved, the old image is still in GHCR.

1. Railway → service `iron_verdict` → environment `production` → **Settings → Source → Source Image** → edit (pencil), set the tag of `ghcr.io/abti247/iron_verdict:vX.Y.Z` back to `v<previous>`, save.
2. Deploy the change (if Railway stages it as a pending change, apply/deploy it). Wait until the new deployment is *Active*.
3. Check: `https://iron-verdict.com/health` answers `{"status":"ok"}`, the landing page footer shows the `sha-<commit>` of `v<previous>`, a test session works (create, join as a judge).
4. Open an issue for the faulty release. Do not delete its tag or image — it is the evidence.

## Checklist before a competition

- [ ] Production runs a release tag (`vX.Y.Z`, not `main` or `sha-…`); footer version matches that release.
- [ ] The previous release tag is noted (rollback target) and still listed under GitHub → Releases.
- [ ] No deploy planned during the competition: an open approval *Produktion* stays unapproved until the competition is over.
- [ ] Once, for the first competition on a release after v0.2.1: hard-reload every judge and display device (Ctrl+Shift+R, or clear the site data on phones). Static files are revalidated on every load since then (#135, #145); devices may still hold older files the browser considers fresh.
- [ ] `https://iron-verdict.com/static/js/app.js` answers `cache-control: no-cache` (network tab or `curl -sI`; if it shows `max-age=…`, fix Cloudflare as described under One-time setup).
- [ ] Uptime check green in Grafana, and a test alert arrived on the phone via Telegram (Firing and Resolved; [docs/monitoring.md](monitoring.md), Test alert).
- [ ] `/health` ok; a test session works end to end: 3 judges + display, vote, result, Next Lift, reload of a judge.
- [ ] For VPortal competitions: `/vportal` session connects to the federation and shows the current lifter on the display.
- [ ] Fallback known: the app can run locally on a laptop on the venue Wi-Fi (README, "Running locally on competition WiFi").
