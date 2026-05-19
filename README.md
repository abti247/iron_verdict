# Iron Verdict

A real-time powerlifting competition judging application.

## Features

- **Real-time Judging:** 3 judges make independent decisions (White/Red/Blue/Yellow lights) and are able to pick a specified reason
- **IPF-compliant:** Results are shown only after all three judges lock in, matching the simultaneous-lights rule; reasons follow the IPF Technical Rules (effective 01 March 2026, v3)
- **Live Display:** Synchronized display screen shows all judge lights and reason to audience
- **Timer System:** 60-second countdown controlled by head judge
- **Judge Reconnect:** Judges can rejoin seamlessly after an accidental disconnect without losing their vote or getting a "Role taken" error
- **Connectivity Indicators:** Head judge screen shows live L/R connection status for the other two judges
- **Session-based:** Simple 8-character codes, no accounts needed
- **Lightweight:** No database — sessions live in memory and expire after 4 hours of inactivity, with optional JSON snapshot persistence across restarts

## Tech Stack

- **Backend:** FastAPI with WebSockets
- **Frontend:** HTML + Alpine.js
- **Session Storage:** In-memory with optional JSON snapshot persistence
- **Real-time Communication:** WebSockets

## Running a Competition

1. **Create Session:**
   - One person opens the app and clicks "Create New Session"
   - Note the 8-character session code

2. **Join as Judges:**
   - Three judges enter the session code — or scan the QR code shown on the host's Select Role screen
   - Select their position: Left Judge, Center Judge (Head), or Right Judge
   - Head judge decides if all judges are required to pick a reason and if this is displayed to the audience

3. **Join as Display:**
   - Display device enters session code and selects "Display"
   - This screen shows the lights to the audience

4. **During Competition:**
   - Head judge starts 60-second timer when lifter is ready
   - Judges make their calls (White/Red/Blue/Yellow)
   - Each judge locks in their decision
   - When all 3 judges lock in, results appear on all screens
   - Head judge clicks "Next Lift" to reset for next attempt

5. **End Session:**
   - Head judge clicks "End Session" when competition is complete

## Deployment

### Docker

Requirements: Docker

```bash
docker build -t iron_verdict .
docker run -p 8000:8000 \
  -e ALLOWED_ORIGIN=https://your-domain.com \
  -v ./data:/data \
  iron_verdict
```

The `-v` flag mounts a persistent directory for session snapshots (`/data/sessions.json`). Without it, active sessions are lost on container restart. The `/data` directory is created inside the container automatically.

On Windows PowerShell, replace `./data` with `${PWD}/data`.

For local development without persistence:
```bash
docker run -p 8000:8000 iron_verdict
```

For all available environment variables see [Configuration](#configuration).

### Docker Compose

For local hosting, the included `docker-compose.yml` is the simplest path — it bind-mounts `./data` for snapshot persistence and sets sensible defaults:

```bash
docker compose up
```

Edit `docker-compose.yml` to override `ALLOWED_ORIGIN` or other environment variables before running in any setting where the app is reachable beyond your machine.

### Running locally on competition WiFi

If the venue's uplink is slow or unreliable, you can host the app on your laptop and have judges/display connect over the local WiFi. Judging traffic (votes, timer, lights) then flows directly over the LAN — only optional VPortal lifter-info polling crosses the internet, and it is not on the critical path.

1. Start the server on your laptop with `docker compose up` or `python run.py`. The default `HOST=0.0.0.0` already binds to all interfaces.
2. Find your laptop's WiFi IPv4 address (`ipconfig` on Windows, `ifconfig`/`ip addr` on macOS/Linux). Example: `192.168.1.42`.
3. **Open the app on the laptop using that LAN IP, not `localhost`** — i.e. `http://192.168.1.42:8000`. The QR code on the Select Role screen is generated from whatever URL you loaded, so creating the session via `localhost` would produce a QR that no other device can reach.
4. Allow inbound TCP port 8000 in your OS firewall on the **Private** network profile. On Windows, the first run typically triggers a prompt.
5. Disable laptop sleep / lid-close-suspend and keep the machine on power for the duration of the event.

Tips:
- Reserve your laptop's IP in the router's DHCP settings so a mid-event lease change can't break shared QR codes.
- The default `ALLOWED_ORIGIN=*` is fine for LAN use; do not expose this configuration to the public internet.

### Railway

1. Deploy from your GitHub repository.
2. Add a **Volume** mounted at `/data` (Railway dashboard → Storage).
3. Set the `ALLOWED_ORIGIN` environment variable to your Railway-assigned domain.

All other settings default to sensible production values.

## Development

### Requirements

- Python 3.11+

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd iron-verdict
```

2. Create and activate a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
.venv\Scripts\activate     # Windows
```

3. Install the package in editable mode with dev dependencies:
```bash
pip install -e ".[dev]"
```

4. (Optional) Configure environment variables:
```bash
cp .env.example .env
```

### Start the server

```bash
python run.py
```

Or directly with uvicorn for auto-reload:
```bash
uvicorn iron_verdict.main:app --reload
```

The application will be available at http://localhost:8000

### Run Tests

Run all tests (unit + E2E):
```bash
pytest
```

Run only unit tests:
```bash
pytest tests/ --ignore=tests/e2e/
```

Run E2E tests (requires Playwright's Chromium browser):
```bash
playwright install chromium   # first time only
pytest tests/e2e/
```

## Configuration

All settings are optional and have defaults suitable for local development.

| Variable | Default | Description |
|---|---|---|
| `HOST` | `0.0.0.0` | Host to bind to |
| `PORT` | `8000` | Port to listen on |
| `ALLOWED_ORIGIN` | `*` | CORS/WebSocket allowed origin — set to your domain in production |
| `SESSION_TIMEOUT_HOURS` | `4` | Hours of inactivity before a session expires |
| `DISPLAY_CAP` | `20` | Maximum number of display connections per session |
| `SNAPSHOT_PATH` | `/data/sessions.json` | Path for session persistence snapshot — mount `/data` as a volume to survive restarts |
| `LOG_LEVEL` | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `VPORTAL_FETCH_INTERVAL_MS` | `3000` | How often the display polls VPortal for the current lifter, in milliseconds. Clamped to 2000ms minimum. Only used for sessions created via `/vportal`. |
| `TEST_MODE` | unset | When set to `1`, the VPortal proxy allows `localhost`/`127.0.0.1` hosts (for E2E tests). Never set this in production. |
| `EXPOSE_VPORTAL_STAGING` | unset | When set to `1`, the VPortal connect modal exposes a third federation option, **BVDK Staging**, pointing at `staging-bvdk.vportal-online.de`. Use only while you have valid staging credentials; leave unset otherwise so end users don't see an unusable option. |

## VPortal integration (BVDK / ÖVK)

Iron Verdict can optionally pull the current lifter, attempt, and weight from the VPortal competition-management software used by the German (BVDK) and Austrian (ÖVK) federations, and display it on the projector view.

To use it:

1. Open `<your-iron-verdict-url>/vportal` instead of the normal landing page.
2. Create a session as usual.
3. On the Select Role screen, click **Connect to comp software** and enter your VPortal operator credentials.
4. Pick your stage. The display screen will now show lifter info alongside the lights/timer/verdict.

Iron Verdict never writes back to VPortal — verdicts are still recorded manually by the official scorekeeper on the VPortal side.

## Project Structure

```
iron-verdict/
├── src/iron_verdict/        # FastAPI app, session/connection
│   │                          managers, VPortal proxy
│   └── static/              # Frontend (HTML + Alpine.js,
│                              CSS, i18n locales, vendored JS)
├── tests/                   # Backend + JS unit tests
│   └── e2e/                 # Playwright end-to-end tests
├── docs/
│   ├── architecture.md      # System architecture & rationale
│   ├── testing.md           # Test layout & regression strategy
│   ├── backlog.md
│   ├── e2e-known-risks.md
│   └── vportal-fake-server-fidelity.md
├── pyproject.toml
├── package.json             # Vitest config for JS unit tests
├── Dockerfile
├── docker-compose.yml
└── run.py
```

See [docs/architecture.md](docs/architecture.md) for module-level detail.

## License

[MIT](LICENSE)
