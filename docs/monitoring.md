# Monitoring

Production is watched from Grafana Cloud (free tier, region EU). Grafana pulls everything — the uptime check calls `/health`, the metrics scrape calls `/metrics` — so the app opens no connection to Grafana and a Grafana outage cannot affect a competition. Only **critical** alerts are delivered (Telegram); warnings show on the dashboard and are reviewed by hand every Monday morning.

How the metrics are produced: [architecture.md, Observability](architecture.md#observability).

## 1. Grafana stack, uptime check and Telegram

Set up in [#132](https://github.com/abti247/iron_verdict/issues/132): stack, synthetic `/health` check, Telegram contact point and the notification policy (`severity=critical` → Telegram, everything else is not delivered). The steps follow there.

## 2. Metrics scrape

1. Generate a token: `openssl rand -hex 32`. Never commit it.
2. Railway → service `iron_verdict` → environment **production** → Variables → `METRICS_TOKEN=<token>` → deploy. The deploy log shows `metrics_enabled` (without it: `metrics_disabled`, the endpoint answers 404).
3. Check: `curl -s -H "Authorization: Bearer <token>" https://iron-verdict.com/metrics | head` shows lines starting with `# HELP iron_verdict_…`. Without the header the answer is 404.
4. Grafana → **Connections → Add new connection → Metrics Endpoint**:
   - Scrape job name: `iron-verdict-prod`
   - Scrape job URL: `https://iron-verdict.com/metrics`
   - Scrape interval: every minute
   - Authentication: **Bearer**, token from step 1
   - **Test Connection** → must succeed. A 403 or a challenge page means Cloudflare's Bot Fight Mode blocks Grafana; the decision for that is recorded in #132. Then **Save scrape job**.
5. Grafana → Explore → `iron_verdict_build_info` shows the running version within two minutes.

Staging stays without `METRICS_TOKEN` (endpoint off), so it neither counts towards the free tier nor raises alerts.

`RATE_LIMIT_METRICS` (default `30/minute` per client IP) leaves room for the scrape plus manual checks; no need to change it.

## 3. Dashboard

The dashboard is versioned in the repo: [grafana/iron-verdict-dashboard.json](grafana/iron-verdict-dashboard.json).

- Import: Grafana → **Dashboards → New → Import** → upload the file → keep the uid `iron-verdict` → **Import**. Pick the Prometheus data source of the stack (`grafanacloud-<stack>-prom`) in the *Data source* selector at the top; *Job* defaults to all jobs that report `iron_verdict_build_info`.
- Update: edit in Grafana, then **Share → Export → Export for sharing externally: off → Save to file**, replace the JSON in the repo and commit it in the same PR as the change that needs it. Importing a newer file over the old one (same uid) overwrites it.

Sections:

| Section | Content |
|---|---|
| Now | Status tiles (scrape up, sessions, judges, displays, version, snapshot age), **What stands out now** (every firing or pending alert rule, critical and warning), votes per minute and rejections, lost connections by reason, memory (orange from 512 MB, red from 3 GB), HTTP status classes, errors, CPU, sessions/judges/displays over time |
| Weekly review (last 7 days) | Fixed 7-day window regardless of the time picker: scrape availability, max sessions, votes, rejected votes, unhandled exceptions, snapshot failures, max memory, max snapshot age, lost connections and HTTP responses by class, plus the week as curves |

Shown only as curves, never as alert rules: single heartbeat drops (normal on venue Wi-Fi), rate-limit hits and unknown session codes (both in 4xx), rejected cross-site connections (in the logs).

## 4. Alert rules

Create them in Grafana → **Alerting → Alert rules → New alert rule**, data source = the stack's Prometheus, folder `Iron Verdict`, evaluation group `iron-verdict` every 1 minute. The label `severity` decides delivery via the notification policy from #132.

Replace `JOB` with the scrape job name from step 2 (`iron-verdict-prod`; Grafana may prefix it — check `up` in Explore).

**Critical** (`severity=critical` → Telegram). All except the first apply only while a session exists, so nights without a competition stay quiet.

| Name | Query (alert when true) | Pending period | No data |
|---|---|---|---|
| PROD metrics unreachable | `max(up{job="JOB"}) < 1` | 3m | Alerting |
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

**Test alert:** in the *Memory above 3 GB* rule temporarily change the threshold to `> 1` and the condition `sum(iron_verdict_sessions_active…) > 0` to `>= 0`, save, wait for the Telegram message, then restore both and wait for the resolved message.

## 5. Weekly review (Monday morning)

Open the dashboard, section **Weekly review**, and go through:

1. **What stands out now** empty? Otherwise follow up each rule.
2. Scrape availability ≥ 99.9 %? Gaps without a deploy → check Railway and Cloudflare.
3. Unhandled exceptions, snapshot failures > 0 → find them in the Railway logs (`unhandled_exception`, `snapshot_save_failed`) and open an issue.
4. Max memory and the weekly memory curve: a steady climb without restarts points to a leak.
5. Lost connections by reason: many `heartbeat_stale` / `client` during a competition point to the venue Wi-Fi; `flood`, `error` or `heartbeat_send_failed` deserve an issue.
6. Rejected votes and 4xx/5xx: a jump compared to earlier weeks → look up the codes in the logs.
7. Note anything unusual in an issue; adjust thresholds here and in the dashboard if they proved wrong.
