# Monitoring

Runbook for the maintainer. Production is watched from outside by Grafana Cloud (free tier, region EU): an uptime check calls `https://iron-verdict.com/health` every minute, and a failed check reaches the maintainer's phone via Telegram. Railway calls `/health` only during a deploy, never afterwards ([Railway docs](https://docs.railway.com/reference/healthchecks)), so without this check nobody notices a hung or crashed app until people at the venue report it. Architecture view: [docs/architecture.md](architecture.md), *Observability*.

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

If it stays red, open the log of a failed run (click a bar, tab per location): status `403` or a "Just a moment…" page means Cloudflare blocks the probes — see *Cloudflare Bot Fight Mode* below.

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

Production has Bot Fight Mode on (see [docs/architecture.md](architecture.md), *Edge*). On the free plan it cannot be switched off for single requests by a rule ([Cloudflare docs](https://developers.cloudflare.com/waf/feature-interoperability)), so it may challenge the Grafana probes.

**Result (2026-10-26, #132):** the probes pass with Bot Fight Mode on — both locations reach the app through Cloudflare (log: Cloudflare IP, status 200). Bot Fight Mode stays on. If a later check run shows `403` or a challenge page, the fallback is to turn Bot Fight Mode off (Security → Bots); the app has its own rate limits and origin check. A Railway domain as a way around Cloudflare is not an option (see *Why `iron-verdict.com`* above).
