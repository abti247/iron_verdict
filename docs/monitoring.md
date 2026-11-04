# Monitoring

Runbook for the maintainer. Production is watched from outside by Grafana Cloud (free tier, region EU): an uptime check calls `https://iron-verdict.com/health` every minute, and a failed check reaches the maintainer's phone via Telegram. Railway calls `/health` only during a deploy, never afterwards ([Railway docs](https://docs.railway.com/reference/healthchecks)), so without this check nobody notices a hung or crashed app until people at the venue report it. Architecture view: [docs/architecture.md](architecture.md), *Observability*.

Grafana pulls uptime and metrics — the uptime check calls `/health`, the metrics scrape calls `/metrics` (#133). Logs are the exception: the app pushes a copy without IP addresses to Grafana Loki (#134) from a background thread that the competition never waits on, so a Grafana outage cannot affect a competition either (see *Logs* below). How the metrics are produced: [architecture.md, Observability](architecture.md#observability).

What is set up (#132):

| Piece | Setting |
|---|---|
| Stack | Grafana Cloud `calmcabinet2149.grafana.net`, free tier, region EU Germany (`prod-eu-west-2`) |
| Uptime check | HTTP `GET https://iron-verdict.com/health`, every 1 min, from Frankfurt and London; success = status 200 and body contains `"status":"ok"` |
| Alert rule | "PROD nicht erreichbar", label `severity=critical`: fires when **both** locations fail in 2 consecutive minutes; a resolved message follows when the check is green again |
| Delivery | Contact point Telegram only. Notification policy: `severity=critical` → Telegram, everything else muted. No e-mail contact point |

Only critical alerts are delivered. Non-urgent warnings (metrics #133, logs #134) stay in the dashboard and are reviewed by hand on Monday mornings.

*Why `iron-verdict.com` and not a Railway domain:* the check walks the judges' path — DNS, Cloudflare, TLS, app. Production has no `*.up.railway.app` domain, and adding one would make the whole app reachable past Cloudflare.

*Why both locations:* a network problem at a single Grafana probe location must not wake anyone; an outage of the app, Cloudflare or DNS shows from both.

*Budget:* 2 locations × 1 check per minute = 89,280 executions in a 31-day month; the free tier allows 100,000 API-check executions. Adding a location or a second check every minute exceeds it — recalculate first.

No secret goes into this repository. The Telegram bot token lives only in Grafana (and the maintainer's password manager).

## One-time setup

Menu names and screens as seen at the setup on 2026-10-26 (Grafana Cloud, Synthetic Monitoring with the step-by-step check editor); they may move, the settings stay the same.

### 1. Stack

1. Create a Grafana Cloud account at grafana.com (sign-in with GitHub works). It starts as a 14-day trial and falls back to the free tier on its own — choose no plan.
2. Grafana creates a stack with a generated name (production: `calmcabinet2149.grafana.net`). Check its region: grafana.com → *Cloud portal* → the stack → *Prometheus* → **Details** → *Grafana Cloud cluster / region* must be an EU region (production: `EU Germany - prod-eu-west-2`). If not, add a stack in an EU region and delete the generated one.

### 2. Telegram bot and chat ID

1. In Telegram, open **@BotFather** → `/newbot` → name (e.g. "Iron Verdict Alerts") and username (must end in `bot`). BotFather answers with the **bot token** (`123456:ABC…`). Store it in the password manager.
2. Open the **new bot's** chat (link `t.me/<username>` in BotFather's answer), tap *Start* and send any message. A bot cannot write to a chat that never wrote to it.
3. Get the **chat ID**: open `https://api.telegram.org/bot<token>/getUpdates` in a private browser window and read the number after `"chat":{"id":`. The URL contains the token — do not share it or paste it anywhere else.
   - `{"ok":true,"result":[]}` means the bot has received nothing yet — usually the message went to another chat (e.g. BotFather). `https://api.telegram.org/bot<token>/getMe` shows which bot the token belongs to.

### 3. Contact point

Alerts & IRM → Alerting → **Contact points** → *Create contact point*:

- Name: `telegram`
- Integration: **Telegram**, *BOT API Token* = bot token, *Chat ID* = chat ID
- *Disable resolved message*: **off** (the all-clear is wanted)
- *Test* → a test message arrives in Telegram → *Save*

Delete the preset e-mail contact point (`grafana-default-email`) once the default policy no longer uses it (step 4).

### 4. Notification policy

Alerts & IRM → Alerting → **Notification policies**:

1. Tab **Time intervals** → *New time interval*: name `always`, *Days of the week*: click all seven days (Mon–Sun), leave time range, location, days of the month, months and years empty. Save. The list shows "Times: All, Weekdays: Mon … Sun, … Years: All".
2. Tab **Notification policies** → *Default policy* → *More* → *Edit* → *Default contact point* `telegram`. Leave grouping as preset.
3. *Default policy* → **Add route**: matcher `severity` `=` `critical`, contact point `telegram`, *Continue matching* off, no mute timing.
4. *Default policy* → **Add route** again (same level, not under the first route): matcher `severity` `!=` `critical`, contact point `telegram`, *Continue matching* off, **Mute timings** `always`. This also catches alerts without a `severity` label.

Do not use *New notification policy* — it creates a second, separate policy tree. Result: the default policy shows two routes, the second one "Muted when always". The default policy then receives nothing: every alert matches one of the two routes.

The time interval does not affect when the check runs or when the rule fires — it only mutes notifications of the route it is attached to.

### 5. Uptime check

Testing & synthetics → Synthetics → **Checks** → *Create new check* → **API Endpoint**. The editor has five steps:

1. **Request:** request type **HTTP**, job name `iron-verdict-prod` (the alert rule filters on it), request target `https://iron-verdict.com/health`, method `GET`, follow redirects off.
2. **Uptime:**
   - *Valid status codes* `200`; *Valid HTTP versions* empty; *SSL options* "Ignore SSL" (the certificate is still verified); *Compression* "None"; *Timeout* as preset (3 s — `/health` answers in milliseconds).
   - *Regexp validation*: source **Body**, match condition `"status":"ok"`, **Invert on**, *Allow missing* off. Without *Invert* the check fails when the body *does* match (the log then shows "Body matched regular expression" → "Check failed").
3. **Labels:** none.
4. **Execution:** EMEA **Frankfurt, DE** and **London, UK**; frequency **1m**; *Publish full set of metrics* off. The estimate shows 89,280 executions per month.
5. **Alerting:** leave all per-check alerts (failed checks, TLS certificate, latency) off — the alert rule below replaces them.

Save. After 2–3 minutes the check dashboard shows green bars for both locations. A single "No result found from London/Frankfurt" for one minute is normal (the run fell into the next minute).

If it stays red, open the log of a failed run (click a bar, tab per location): status `403` or a "Just a moment…" page means Cloudflare blocks the probes — Bot Fight Mode is off since #205, so look in Security → Analytics → Events for the Cloudflare feature that acted; background in *Cloudflare Bot Fight Mode* below.

### 6. Alert rule

Alerts & IRM → Alerting → **Alert rules** → *New alert rule*:

1. Name: `PROD nicht erreichbar`
2. Query and condition: data source `grafanacloud-<stack>-prom`, editor **Code**:

   ```promql
   max by (job) (last_over_time(probe_success{job="iron-verdict-prod"}[90s]))
   ```

   *Run queries* shows one row `{job="iron-verdict-prod"}` with `1`. *Alert condition*: `WHEN QUERY IS BELOW 1`; *Preview alert rule condition* shows **Normal** (re-run the preview after changing the condition — an old preview may still show *Firing*).

   `probe_success` is 1 per location for a passed run and 0 for a failed one; the maximum over the locations is 0 only when **both** failed. `last_over_time(…[90s])` takes each location's latest run (one per minute), bridges a single missing result and drops a series that stopped reporting; a plain instant query would keep a stopped series at its last value for 5 minutes.
3. Folder: *New folder* `Iron Verdict`. Labels: *Add labels* → type `severity`, Enter → type `critical`, Enter → *Save*.
4. Evaluation: *New evaluation group* `uptime`, interval **1m**; *Pending period* **1m** (the first failed evaluation goes to *Pending*, the second one a minute later fires — 2 failed runs in a row); *Keep firing for* None; *Configure no data and error handling* as preset.
   - If the check stops delivering data, the rule sends its own `DatasourceNoData` alert with the same labels; a query error sends `DatasourceError`. Both reach Telegram and mean "monitoring broken", not "PROD down" — check Grafana, not the app.
5. Notifications: *Advanced options* on → recipient **Default policy** (the notification policy tree, not a single contact point). *Alert instance routing preview*: "Delivered to telegram" with `severity critical`.
6. Message: *Summary* `PROD nicht erreichbar: https://iron-verdict.com/health antwortet nicht`; *Description* `Rollback: docs/release.md, Abschnitt Rollback. Fallback: Laptop im Hallen-WLAN (README).`; *Runbook URL* `https://github.com/abti247/iron_verdict/blob/main/docs/release.md#rollback`.

Save. The rule shows *Normal* in the list.

The job filter deliberately leaves out `instance` (the URL), so the test alert below still matches while the check points at another path. Changing the target starts a new series; the old one drops out of the query after 90 s thanks to `last_over_time`.

## Test alert

Run after the setup and before every competition (see [docs/release.md](release.md), *Checklist before a competition*):

1. Edit the check: change the target to `https://iron-verdict.com/health-test-404` (does not exist, answers 404). Save.
2. After about 3½ minutes (old series drops out, 2 failed runs, then grouping; observed at the first test on 2026-10-26) Telegram shows **Firing** with the labels, summary, description and runbook link. The `**Firing**` asterisks are Grafana's markdown, shown as plain text — harmless.
3. Set the target back to `https://iron-verdict.com/health`. Save.
4. About 4 minutes later (observed 2026-10-26) Telegram shows **Resolved**, and the check is green again. The rule is back to *Normal* after the first green run; Grafana sends changes to an alert it already reported at most every 5 minutes (*group interval* of the default policy), so Resolved takes 1–5 minutes.

Forgetting step 3 leaves the alert firing — the Telegram message is the reminder.

Reading the message:

- `Value: A=0, C=1` — `A` is the query (0 = both locations failed, 1 = at least one passed), `C` the condition `IS BELOW 1` (1 = met, the rule fires). The resolved message shows `A=1, C=0`. The *summary* line says the same in words.
- In a real outage the message arrives about 2–3½ minutes after the app stopped answering: 2 evaluations with both locations failed, plus up to 30 s grouping (the test takes longer because the old series first has to drop out). Evaluations are not synchronised with the runs, so rarely one failed run per location is enough — an early alert, never a missed one.
- One Firing per outage, repeated every 4 hours while it lasts (*repeat interval* of the default policy), then one Resolved. Outages shorter than 2 minutes stay *Pending* and send nothing.
- The Resolved message exists because *Disable resolved message* is off on the contact point.
- *Silence* links to a silence for this alert: while it is active, a real outage sends nothing either. Use it only for planned maintenance, with a short duration.

## Cloudflare Bot Fight Mode

Production has Bot Fight Mode **off** since 2026-11-04 (#205): it challenged the release chain's production check from GitHub runners ([docs/release.md](release.md), One-time setup). The results below were taken while it was on. On the free plan it cannot be switched off for single requests by a rule ([Cloudflare docs](https://developers.cloudflare.com/waf/feature-interoperability)). While it was on, it could have challenged the Grafana probes; with it off they no longer depend on it.

**Result (2026-10-26, #132):** the probes pass with Bot Fight Mode on — both locations reach the app through Cloudflare (log: Cloudflare IP, status 200). The fallback named then — turning it off, since the app has its own rate limits and origin check — is what #205 did. A Railway domain as a way around Cloudflare is not an option (see *Why `iron-verdict.com`* above).

**Metrics scrape (2026-10-30, #133):** Grafana's Metrics Endpoint scrape also passes with Bot Fight Mode on (requests reach the app, log: `GET /metrics` 200).

## Metrics scrape

Menu names and screens as seen at the setup on 2026-10-30/31 (#133).

1. Generate a token: `openssl rand -hex 32`. Never commit it.
2. Railway → service `iron_verdict` → environment **production** → Variables → `METRICS_TOKEN=<token>` → deploy. The deploy log shows `metrics_enabled` (without it: `metrics_disabled`, the endpoint answers 404).
3. Check: `curl -s -H "Authorization: Bearer <token>" https://iron-verdict.com/metrics | head` shows lines starting with `# HELP` (process metrics first, `iron_verdict_…` further down). Without the header, or with a wrong token, the answer is 401.
4. Grafana → **Connections → Add new connection → Metrics Endpoint**:
   - Scrape job name: `iron-verdict-prod-metrics` (not `iron-verdict-prod` — that is the uptime check's job, and both would share the `job` label)
   - Scrape job URL: `https://iron-verdict.com/metrics`
   - Scrape interval: every minute
   - Authentication: **Bearer**, token from step 1
   - **Test Connection** → "All good! Successfully scraped metrics from URL". Then **Save Scrape Job** (and **Install** if offered).
     - Test Connection first asks *without* the token and sends it only after a `401` with `WWW-Authenticate` (#185). Every regular scrape sends the token right away, so the scrape adds no 401s to the 4xx curve.
     - It failing with "did not return a valid response": find the `GET /metrics` lines of that click in the Railway log. None → Cloudflare blocks Grafana (did not happen on 2026-10-30: Bot Fight Mode lets the scrape through). `401` without a following `200` → the token in Grafana differs from `METRICS_TOKEN`.
5. Grafana → Explore → `iron_verdict_build_info` shows the running version within two minutes. Note its `job` label: Grafana prefixes the scrape job name, in production `integrations/metrics_endpoint/3711045-metrics-endpoint-iron-verdict-prod-metrics` (the label `scrape_job` keeps the plain name). The alert rules below filter on this full value.

Staging stays without `METRICS_TOKEN` (endpoint off), so it neither counts towards the free tier nor raises alerts.

`RATE_LIMIT_METRICS` (default `30/minute` per client IP) leaves room for the scrape plus manual checks; no need to change it.

## Logs

Production sends every log line, without `client_ip`, to the stack's Loki (#134). stdout in Railway stays complete (7 days, with IPs); Loki keeps the copy 14 days (free tier). How it works and why: [architecture.md, Observability](architecture.md#observability).

### Setup

Menu names as of 2026-11; they may move, the settings stay the same.

1. grafana.com → *Cloud portal* → the stack → **Loki** → *Details*: note the **URL** (e.g. `https://logs-prod-012.grafana.net`) and the **User** (a number).
2. *Cloud portal* → **Access Policies** → *Create access policy*: name `iron-verdict-logs-write`, realm = the stack, scope **`logs:write` only** → *Create*. Then *Add token* (name `railway-prod`, no expiry or a noted one) and copy it once. Store it in the password manager; never commit it.
3. Railway → service `iron_verdict` → environment **production** → Variables:
   - `LOKI_URL` = URL from step 1 plus `/loki/api/v1/push`
   - `LOKI_USER` = User from step 1
   - `LOKI_TOKEN` = token from step 2

   Deploy. The deploy log shows `log_shipping_enabled` with the Loki host; without the variables it shows `log_shipping_disabled`, and a **warning** `log_shipping_disabled` with `reason` `incomplete_config` means one of the three is missing.
4. Grafana → **Explore** → the Loki data source (`grafanacloud-<stack>-logs`) → `{app="iron-verdict"}`: lines appear within about 10 s (the app sends every 5 s). `{app="iron-verdict"} |= "client_ip"` must return nothing.

Staging stays without the variables (same as `METRICS_TOKEN`), so production logs are not mixed with test runs.

If Grafana refuses or does not answer, the app logs `log_ship_failed` (with `error` and `upstream_status`, e.g. `401` for a wrong user or token) once on stdout and `log_ship_recovered` once it works again. Lines lost for Loki meanwhile are counted in `iron_verdict_log_ship_dropped_total{reason}` (`send_failed`, or `queue_full` after more than 10,000 waiting lines) and are still in Railway.

### Queries

Every line is the JSON of stdout; `| json` turns its fields into labels. Labels on the stream: `app`, `level` (`info`, `warning`, `error`, `critical`), `version`.

| Question | LogQL |
|---|---|
| Everything about session `ABC12345` | `{app="iron-verdict"} \| json \| session_code="ABC12345"` |
| All warnings and errors in the competition window (set the time picker) | `{app="iron-verdict", level=~"warning\|error\|critical"}` |
| Warnings and errors by event name | `sum by (message) (count_over_time({app="iron-verdict", level=~"warning\|error\|critical"} \| json [$__auto]))` |
| One event, e.g. lost connections | `{app="iron-verdict"} \| json \| message="role_disconnected"` |
| Rejected votes by code | `sum by (code) (count_over_time({app="iron-verdict"} \| json \| message="vote_rejected" [$__auto]))` |

### Export after a competition

Loki keeps 14 days. To keep a competition for later, export its time window within that period:

- **Small windows** (up to the Explore line limit, 5,000 lines): Explore → query `{app="iron-verdict"}`, set the time range and *Line limit* → *Download* → `json` or `txt`.
- **A whole competition day:** [`logcli`](https://grafana.com/docs/loki/latest/query/logcli/) with a **separate, short-lived** token with `logs:read` (create it as in step 2, delete it afterwards — the write token cannot read):

  ```bash
  logcli query '{app="iron-verdict"}' --addr=https://logs-prod-012.grafana.net --username=<User> --password=<read token> --from=2026-11-14T07:00:00Z --to=2026-11-14T20:00:00Z --limit=0 --batch=5000 --forward --output=raw --quiet > competition-2026-11-14.jsonl
  ```

  Times are UTC. The file has one JSON line per log line, without IPs; store it outside the repository.

## Dashboard

The dashboard is versioned in the repo: [grafana/iron-verdict-dashboard.json](grafana/iron-verdict-dashboard.json).

- Import: Grafana → **Dashboards → New → Import** → upload the file → keep the uid `iron-verdict` → *Folder* **`Iron Verdict`** (the alert folder; importing into the top level clashes with that folder's name: "A dashboard or a folder with the same name already exists" — do not click *Import (Overwrite)* for that) → **Import**. Pick the Prometheus data source of the stack (`grafanacloud-<stack>-prom`) in the *Data source* selector at the top and the Loki one (`grafanacloud-<stack>-logs`) in *Logs data source*; *Job* defaults to all jobs that report `iron_verdict_build_info`.
- Update: edit in Grafana, then **Share → Export → Export for sharing externally: off → Save to file**, replace the JSON in the repo and commit it in the same PR as the change that needs it. Importing a newer file over the old one (same uid) overwrites it.

Sections:

| Section | Content |
|---|---|
| Now | Status tiles (scrape up, sessions, judges, displays, version, snapshot age — orange from 3 min, red from 5 min: the app sets it every minute and Grafana scrapes every minute, so up to about 2½ min is normal), **What stands out now** (every firing or pending alert rule, critical and warning), votes per minute and rejections, lost connections by reason, memory (orange from 512 MB, red from 3 GB), HTTP status classes, errors, CPU, sessions/judges/displays over time, VPortal failures by result plus GraphQL retries, VPortal upstream time (GraphQL p50/p95, login p95; orange from 2 s, red at the 5 s timeout), log lines not sent to Loki (in *Errors*), **Logs** (all lines, newest first) |
| Weekly review (last 7 days) | Fixed 7-day window regardless of the time picker: scrape availability, max sessions, votes, rejected votes, unhandled exceptions, snapshot failures, max memory, max snapshot age, lost connections and HTTP responses by class, VPortal failures by result and GraphQL retries, warnings and errors from the logs by event name, log lines not sent to Loki, plus the week as curves |

Shown only as curves, never as alert rules: single heartbeat drops (normal on venue Wi-Fi), rate-limit hits and unknown session codes (both in 4xx), rejected cross-site connections (in the logs), VPortal failures and upstream time (decided in #181: curves and the weekly review only, no rule).

## Metrics alert rules

Create them in Grafana → **Alerts & IRM → Alerting → Alert rules → New alert rule**, data source = the stack's Prometheus, editor **Code**, folder `Iron Verdict`, evaluation group **`metrics`** every 1 minute (next to the uptime rule's group `uptime`). The label `severity` decides delivery via the notification policy (*One-time setup*, step 4); enter it with *Add labels* → type the key, Enter → type the value, Enter. Every rule needs it — check that the rule's page shows *Labels: severity …* after saving. Notifications: *Advanced options* → recipient **Default policy**, as for the uptime rule.

Replace `JOB` with the full `job` label from *Metrics scrape*, step 5 (production: `integrations/metrics_endpoint/3711045-metrics-endpoint-iron-verdict-prod-metrics`).

How the condition is set, and why it differs between the first rule and the rest:

- **PROD metrics unreachable:** the query has no comparison; *Alert condition* `WHEN QUERY IS BELOW 1`; *no data* → **Alerting** (the series vanishing, e.g. a deleted scrape job, is also an alert). With `< 1` in the query instead, a healthy scrape returns no rows and *no data → Alerting* fires all the time.
- **All other rules:** the comparison is in the query, which returns a row only when something is wrong; *Alert condition* stays at the preset `IS ABOVE 0`; *Run queries* shows **No data** when healthy. Under *Configure no data and error handling*: *no data* → **OK** (Normal), *error* → **Error**. With *no data* → *NoData*, Grafana sends a `DatasourceNoData` alert with the rule's labels — for a critical rule a Telegram message every night without a competition.

**Critical** (`severity=critical` → Telegram). All except the first apply only while a session exists, so nights without a competition stay quiet.

| Name | Query | Pending period | No data |
|---|---|---|---|
| PROD metrics unreachable | `max(up{job="JOB"})`, condition `IS BELOW 1` | 3m | Alerting |
| Snapshot older than 5 minutes | `(time() - max(iron_verdict_snapshot_last_ok_timestamp_seconds{job="JOB"})) > 300 and on() sum(iron_verdict_sessions_active{job="JOB"}) > 0` | 2m | OK |
| Memory above 3 GB | `max(process_resident_memory_bytes{job="JOB"}) > 3 * 1024^3 and on() sum(iron_verdict_sessions_active{job="JOB"}) > 0` | 5m | OK |

*Why 2 minutes for the snapshot:* after a restart the timestamp is 0 until the first snapshot tick (60 s); restored sessions would otherwise fire the alert on every deploy. *Why 3 GB:* the instance limit is 4 GB; normal use is about 35–40 MB. Thresholds get revisited after a few weeks of real values.

**Warning** (`severity=warning` → not delivered; visible in "What stands out now" and the weekly review):

| Name | Query (alert when true) | Pending period |
|---|---|---|
| Unhandled exceptions | `sum(increase(iron_verdict_unhandled_exceptions_total{job="JOB"}[10m])) > 0` | 0s |
| Snapshot write failed | `sum(increase(iron_verdict_snapshot_failures_total{job="JOB"}[10m])) > 0` | 0s |
| Memory above 512 MB | `max(process_resident_memory_bytes{job="JOB"}) > 512 * 1024^2` | 15m |
| Many 5xx | `sum(increase(iron_verdict_http_requests_total{job="JOB", status_class="5xx"}[10m])) > 5` | 0s |

Summaries used in production (German, like the uptime rule): *PROD-Metriken nicht abrufbar: Grafana erreicht /metrics seit 3 Minuten nicht*; *Sitzungs-Sicherung älter als 5 Minuten, während ein Wettkampf läuft*; *Speicher über 3 GB während eines Wettkampfs, Absturz droht (Limit 4 GB)*; the warnings carry the name in German. The critical rules also have a description with the first thing to check.

After saving, the list shows all rules *Normal* under `Iron Verdict` → `metrics`. A rule saved with a wrong condition shows *Firing* in the preview below the threshold — fix it before the pending period runs out.

**Test alert:** in the *Memory above 3 GB* rule temporarily change the threshold to `> 1` and the condition `sum(iron_verdict_sessions_active…) > 0` to `>= 0`, save. *Firing* arrives on Telegram after about 6 minutes (5 min pending period plus grouping; observed 2026-11-01). Restore both, save; *Resolved* follows within 1–5 minutes.

## Weekly review (Monday morning)

Open the dashboard, section **Weekly review**, and go through:

1. **What stands out now** empty? Otherwise follow up each rule.
2. Scrape availability ≥ 99.9 %? Gaps without a deploy → check Railway and Cloudflare.
3. Unhandled exceptions, snapshot failures > 0 → find them in the Railway logs (`unhandled_exception`, `snapshot_save_failed`) and open an issue.
4. Max memory and the weekly memory curve: a steady climb without restarts points to a leak.
5. Lost connections by reason: many `heartbeat_stale` / `client` during a competition point to the venue Wi-Fi; `flood`, `error` or `heartbeat_send_failed` deserve an issue.
6. VPortal failures by result: `unreachable`, `upstream_error`, `invalid_response` or login reasons other than `rejected` during a competition → find them in the Railway logs (`vportal_upstream_unreachable`, `vportal_upstream_invalid_response`, `vportal_login_failed`) and check the upstream time curve of that day. Login `rejected` is a wrong password; GraphQL retries without `unreachable` are stale connections the retry fixed.
7. Rejected votes and 4xx/5xx: a jump compared to earlier weeks → look up the codes in the logs.
8. **Warnings and errors by event** (from the logs): look up unfamiliar or growing events in Explore (*Logs*, *Queries*). `broadcast_send_failed` and its siblings appear in bursts when several devices of a session leave at once and are usually harmless (sends to sockets that are already closed); if they become so many that they hide real problems, open an issue that separates "already closed" from "open and the send failed" (note in #134). **Log lines not sent to Loki** > 0: `send_failed` → find `log_ship_failed` in Railway; `queue_full` → a burst of more than 10,000 lines in 5 s, worth an issue.
9. Note anything unusual in an issue; adjust thresholds here and in the dashboard if they proved wrong.
