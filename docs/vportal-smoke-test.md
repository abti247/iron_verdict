# VPortal Integration — Manual Smoke Test

Run before any release that touches the VPortal integration (server proxy, client polling, modal flow, display overlay).

## Primary procedure — against `staging-bvdk.vportal-online.de`

Used whenever BVDK staging access is available. Faster turnaround than coordinating a production dummy comp.

### Prerequisites

- BVDK staging credentials (`identity` + `credential`) for `staging-bvdk.vportal-online.de`, plus the staging instance having at least one stage and one active flight set up.
- The Railway deployment configured with `EXPOSE_VPORTAL_STAGING=1` so the modal exposes the staging option. Set this in the Railway dashboard and redeploy.
- Iron Verdict reachable at its production URL.

### Procedure

1. Open `<production-url>/vportal` in a browser. Click **Create New Session**, name it `Smoke Test`.
2. On the Select Role screen, confirm the **Connect to comp software** button is visible.
3. Click it. In the modal:
   - Federation: pick **BVDK Staging**.
   - Username / Password: enter the staging credentials.
   - Click **Log in**. Expect to reach the Stage picker.
   - Pick a stage. Click **Use this stage**.
4. The modal closes. The button now reads **Connected to BVDK_STAGING · &lt;stage name&gt;**.
5. Click **Display Screen**. Wait up to 5 seconds.
6. Confirm the bottom corners populate with the staging competition's current lifter name, club, weight class, age category, discipline, attempt number, and weight.
7. Advance the attempt on the staging side (yourself, if you have admin access, or coordinate with whoever does). Within 5 seconds, the corners should update.
8. Disconnect your laptop from the internet for ~15 seconds. The corners should dim, then the **VPortal disconnected** banner should appear. Reconnect — the banner clears and the corners restore.
9. Click **Disconnect** (re-open the Connect modal first). Confirm the corners disappear and the connect button reverts to **Connect to comp software**.

## Fallback procedure — against `bvdk.vportal-online.de` (production)

Use this when staging access has expired or is otherwise unavailable.

### Prerequisites

- A throwaway VPortal operator account on `bvdk.vportal-online.de`. Coordinate with the Landesverband to provision one bound to a **dummy competition** with at least one stage and one active flight.
- A second person, or VPortal admin access yourself, to advance attempts in the dummy competition.
- The Railway deployment with `EXPOSE_VPORTAL_STAGING` unset (so production users don't see a now-unusable Staging option).
- Iron Verdict reachable at its production URL.

### Procedure

Identical to the primary procedure, except step 3 picks **BVDK** instead of **BVDK Staging** and uses the dummy account's credentials. Step 4 will show **Connected to BVDK · &lt;stage name&gt;**.

## What to watch for (either procedure)

- **No verdict pushed back.** Check the VPortal side: no attempt status changed by Iron Verdict. (Iron Verdict is pull-only; if you see verdicts on the VPortal side that you didn't enter manually, that's a regression.)
- **Server logs** during the test: `vportal_host_rejected`, `vportal_operation_rejected`, and `vportal_fetch_interval_clamped` should not appear.
- **Polling cadence** matches `VPORTAL_FETCH_INTERVAL_MS` (default 3000ms). Browser DevTools → Network tab → filter on `/api/vportal/graphql` to verify.

## Tearing down

- Click **End Session** in Iron Verdict.
- For the production fallback: ask the Landesverband to either retire the dummy comp or keep it for the next smoke test (preferred).
- For staging: nothing to clean up — staging persists across runs.
