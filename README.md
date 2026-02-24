# Iron Verdict

A real-time powerlifting competition judging application.

## Features

- **Real-time Judging:** 3 judges make independent decisions (White/Red/Blue/Yellow lights)
- **Live Display:** Synchronized display screen shows all judge lights to audience
- **Timer System:** 60-second countdown controlled by head judge
- **Session-based:** Simple 8-character codes, no accounts needed
- **Ephemeral:** No database, sessions expire after 4 hours of inactivity

## Tech Stack

- **Backend:** FastAPI with WebSockets
- **Frontend:** HTML + Alpine.js
- **Session Storage:** In-memory (ephemeral)
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
  iron_verdict
```

For all available environment variables see [Configuration](#configuration).

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

### Manual Testing

See [docs/TESTING.md](docs/TESTING.md) for detailed multi-tab testing procedures.

## Configuration

All settings are optional and have defaults suitable for local development.

| Variable | Default | Description |
|---|---|---|
| `HOST` | `0.0.0.0` | Host to bind to |
| `PORT` | `8000` | Port to listen on |
| `ALLOWED_ORIGIN` | `*` | CORS allowed origin — set to your domain in production |
| `SESSION_TIMEOUT_HOURS` | `4` | Hours of inactivity before a session expires |
| `DISPLAY_CAP` | `20` | Maximum number of display connections per session |

## Project Structure

```
iron-verdict/
├── src/iron_verdict/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── session.py           # Session management logic
│   ├── connection.py        # WebSocket connection manager
│   ├── config.py            # Configuration settings
│   └── static/
│       └── index.html       # Frontend UI
├── tests/
│   ├── test_session.py
│   ├── test_connection.py
│   └── test_main.py
├── docs/
│   ├── plans/
│   └── TESTING.md
├── pyproject.toml
├── Dockerfile
└── run.py
```

## License

[Add your license here]
