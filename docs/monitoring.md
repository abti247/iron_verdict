# Monitoring

Runbook for the maintainer. Production is watched from outside by Grafana Cloud (free tier, region EU): an uptime check calls `https://iron-verdict.com/health` every minute, and a failed check reaches the maintainer's phone via Telegram. Railway calls `/health` only during a deploy, never afterwards ([Railway docs](https://docs.railway.com/reference/healthchecks)), so without this check nobody notices a hung or crashed app until people at the venue report it. Architecture view: [docs/architecture.md](architecture.md), *Observability*.

What is set up (#132):

| Piece | Setting |
|---|---|
| Stack | Grafana Cloud, free tier, region EU |
| Uptime check | HTTP `GET https://iron-verdict.com/health`, every 1 min, from 2 EU probe locations; success = status 200 and body contains `"status":"ok"` |
| Alert rule | "PROD nicht erreichbar", label `severity=critical`: fires when **both** locations fail in 2 consecutive minutes; a resolved message follows when the check is green again |
| Delivery | Contact point Telegram only. Notification policy: `severity=critical` → Telegram, everything else muted. No e-mail contact point |

Only critical alerts are delivered. Non-urgent warnings (metrics #133, logs #134) stay in the dashboard and are reviewed by hand on Monday mornings.

*Why `iron-verdict.com` and not a Railway domain:* the check walks the judges' path — DNS, Cloudflare, TLS, app. Production has no `*.up.railway.app` domain, and adding one would make the whole app reachable past Cloudflare.

*Why both locations:* a network problem at a single Grafana probe location must not wake anyone; an outage of the app, Cloudflare or DNS shows from both.

*Budget:* 2 locations × 1 check per minute ≈ 86,400 executions per month; the free tier allows 100,000 API-check executions. Adding a location or a second check every minute exceeds it — recalculate first.

No secret goes into this repository. The Telegram bot token lives only in Grafana (and the maintainer's password manager).

## One-time setup

Menu names follow the Grafana Cloud UI as of October 2026 and may move; the settings stay the same.

### 1. Stack

1. Create a Grafana Cloud account at grafana.com, plan **Free**.
2. Create the stack with region **EU** (e.g. `iron-verdict.grafana.net`).

### 2. Telegram bot and chat ID

1. In Telegram, open **@BotFather** → `/newbot` → name (e.g. "Iron Verdict Alerts") and username (must end in `bot`). BotFather answers with the **bot token** (`123456:ABC…`). Store it in the password manager.
2. Open the new bot in Telegram and send it `/start` (a bot cannot write to a chat that never wrote to it).
3. Get the **chat ID**: open `https://api.telegram.org/bot<token>/getUpdates` in a private browser window and read `result[0].message.chat.id` (a number). The URL contains the token — do not share it or paste it anywhere else. If `result` is empty, send the bot another message and reload.

### 3. Contact point

Alerts & IRM → Alerting → **Contact points** → *Add contact point*:

- Name: `telegram`
- Integration: **Telegram**, *BOT API Token* = bot token, *Chat ID* = chat ID
- *Disable resolved message*: **off** (the all-clear is wanted)
- *Test* → a test message arrives in Telegram → *Save*

Delete the preset e-mail contact point (`grafana-default-email`) once the notification policy below no longer uses it.

### 4. Notification policy

Alerts & IRM → Alerting → **Notification policies**:

1. Mute timings tab → *Add mute timing*: name `always`, *Days of the week* `monday:sunday`, no time range (a whole day on every day). Save.
2. *Default policy* → edit → *Default contact point* `telegram`. Leave grouping as preset.
3. Add a child policy: matcher `severity` `=` `critical`, contact point `telegram`, no mute timing.
4. Add a second child policy below it: matcher `severity` `!=` `critical`, contact point `telegram`, mute timing **`always`**. This also catches alerts without a `severity` label.

The default policy then receives nothing: every alert matches one of the two child policies.

### 5. Uptime check

Testing & synthetics → Synthetics → **Checks** → *Create new check* → **API Endpoint**, request type **HTTP**:

- Job name: `iron-verdict-prod`
- Request target: `https://iron-verdict.com/health`, method `GET`
- Probe locations: two in the EU (e.g. Frankfurt and Paris)
- Frequency: **1 minute**; timeout as preset
- Validation (*Uptime* / *Response*): valid status code `200`; body must match regex `"status":"ok"`; follow redirects off
- Built-in alerting of the check (*Alerts* / alert sensitivity): **none** — the alert rule below replaces it
- Save. After a few minutes the check shows green (uptime 100 %, both locations reachable).

If it stays red, open the check's logs: status `403` or a "Just a moment…" page means Cloudflare blocks the probes — see *Cloudflare Bot Fight Mode* below.

### 6. Alert rule

Alerts & IRM → Alerting → **Alert rules** → *New alert rule*:

- Name: `PROD nicht erreichbar`
- Data source: the stack's Prometheus (`grafanacloud-<stack>-prom`), query (code mode):

  ```promql
  max by (job) (last_over_time(probe_success{job="iron-verdict-prod"}[90s]))
  ```

  `probe_success` is 1 per location for a passed run and 0 for a failed one; the maximum over the locations is 0 only when **both** failed. `last_over_time(…[90s])` takes each location's latest run (one per minute) and drops a series that stopped reporting; a plain instant query would keep a stopped series at its last value for 5 minutes. Check the query in Explore during setup: it shows `1` while the check is green.
- Condition (threshold): `IS BELOW 1`
- Folder `Iron Verdict`, evaluation group `uptime` with interval **1m**
- Pending period: **1m** — the first failed evaluation goes to *Pending*, the second one a minute later fires. That is 2 failed runs in a row.
- *Configure no data and error handling*: as preset (*No Data* / *Error*). If the check stops delivering data, the rule sends its own "no data" alert with the same labels — monitoring that silently stopped is worth knowing about. Likewise a query error sends a `DatasourceError` alert. Both carry `severity=critical` and reach Telegram: a message named `DatasourceNoData` or `DatasourceError` means "monitoring broken", not "PROD down" — check Grafana, not the app.
- Labels: `severity` = `critical`
- Annotations: *Summary* `PROD nicht erreichbar: https://iron-verdict.com/health antwortet nicht`; *Description* `Rollback: docs/release.md, Rollback. Fallback: Laptop im Hallen-WLAN (README).`
- Notifications: use the notification policy (not a fixed contact point). Save.

The job filter deliberately leaves out `instance` (the URL), so the test alert below still matches while the check points at another path. Changing the target starts a new series; the old one drops out of the query after 90 s thanks to `last_over_time`.

## Test alert

Run after the setup and before every competition (see [docs/release.md](release.md), *Checklist before a competition*):

1. Edit the check: change the target to `https://iron-verdict.com/health-test-404` (does not exist, answers 404). Save.
2. After about 3–4 minutes (old series drops out, 2 failed runs, then grouping; replace with the time observed at the first test) Telegram shows **Firing: PROD nicht erreichbar**.
3. Set the target back to `https://iron-verdict.com/health`. Save.
4. A few minutes later Telegram shows **Resolved**, and the check is green again.

Forgetting step 3 leaves the alert firing — the Telegram message is the reminder.

## Cloudflare Bot Fight Mode

Production has Bot Fight Mode on (see [docs/architecture.md](architecture.md), *Edge*). On the free plan it cannot be switched off for single requests by a rule ([Cloudflare docs](https://developers.cloudflare.com/waf/feature-interoperability)), so it may challenge the Grafana probes.

**Status:** open — decided after the first check run, result recorded in #132. If the probes are blocked, the proposal is to turn Bot Fight Mode off (Security → Bots); the app has its own rate limits and origin check. A Railway domain as a way around Cloudflare is not an option (see *Why `iron-verdict.com`* above).
