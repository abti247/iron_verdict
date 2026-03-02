# Iron Verdict

A real-time powerlifting competition judging application.

## Features

- **Real-time Judging:** 3 judges make independent decisions (White/Red/Blue/Yellow lights) and are able to pick a specified reason
- **Live Display:** Synchronized display screen shows all judge lights and reason to audience
- **Timer System:** 60-second countdown controlled by head judge
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
   - Three judges enter the session code
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

For local development without persistence:
```bash
docker run -p 8000:8000 iron_verdict
```

For all available environment variables see [Configuration](#configuration).

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

```bash
pytest
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

## Project Structure

```
iron-verdict/
├── src/iron_verdict/
│   ├── main.py              # FastAPI application, routes, WebSocket handlers
│   ├── session.py           # Session management and persistence
│   ├── connection.py        # WebSocket connection manager
│   ├── config.py            # Configuration from environment variables
│   ├── logging_config.py    # Structured JSON logging
│   └── static/
│       ├── index.html       # Frontend UI
│       ├── css/
│       │   ├── variables.css
│       │   ├── base.css
│       │   ├── layout.css
│       │   ├── components.css
│       │   └── animations.css
│       └── js/
│           ├── app.js       # Alpine.js application state
│           ├── websocket.js # WebSocket client with reconnection
│           ├── handlers.js  # Server message handlers
│           ├── timer.js     # Countdown timer logic
│           ├── demo.js      # Demo mode
│           ├── init.js      # Page initialization
│           └── constants.js # Shared constants
├── tests/
│   ├── test_session.py
│   ├── test_connection.py
│   ├── test_main.py
│   └── test_logging_config.py
├── docs/
│   └── plans/               # Design and implementation plans
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
└── run.py
```

## Roadmap

- [ ] Update for IPF Technical Rule Book (effective date 01 March 2026)
- [ ] Multi-language support
- [ ] CI/CD pipeline (GitHub Actions)

## License

[MIT](LICENSE)
