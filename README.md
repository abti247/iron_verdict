# JudgeMe

A real-time powerlifting competition judging application.

## Features

- **Real-time Judging:** 3 judges make independent decisions (White/Red/Blue/Yellow lights)
- **Live Display:** Synchronized display screen shows all judge lights to audience
- **Timer System:** 60-second countdown controlled by head judge
- **Session-based:** Simple 6-character codes, no accounts needed
- **Ephemeral:** No database, sessions expire after 4 hours of inactivity

## Tech Stack

- **Backend:** FastAPI with WebSockets
- **Frontend:** HTML + Alpine.js
- **Session Storage:** In-memory (ephemeral)
- **Real-time Communication:** WebSockets

## Installation

### Requirements

- Python 3.11+
- pip

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd judgeme
```

2. Create a virtual environment:
```bash
python -m venv .venv
```

3. Activate the virtual environment:

**On Windows:**
```bash
.venv\Scripts\activate
```

**On macOS/Linux:**
```bash
source .venv/bin/activate
```

4. Install dependencies:
```bash
pip install -r requirements.txt
```

5. (Optional) Create `.env` file:
```bash
cp .env.example .env
```

## Usage

### Start the server

```bash
python run.py
```

Or directly with uvicorn:
```bash
uvicorn judgeme.main:app --reload
```

The application will be available at http://localhost:8000

### Running a Competition

1. **Create Session:**
   - One person opens the app and clicks "Create New Session"
   - Note the 6-character session code

2. **Join as Judges:**
   - Three judges enter the session code
   - Select their position: Left Judge, Center Judge (Head), or Right Judge

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

## Development

### Run Tests

```bash
pytest
```

### Run Tests with Coverage

```bash
pytest --cov=judgeme --cov-report=html
```

### Manual Testing

See [docs/TESTING.md](docs/TESTING.md) for detailed multi-tab testing procedures.

## Project Structure

```
judgeme/
├── src/judgeme/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── session.py           # Session management logic
│   ├── connection.py        # WebSocket connection manager
│   ├── config.py            # Configuration settings
│   └── static/
│       └── index.html       # Frontend UI
├── tests/
│   ├── test_session.py      # Session manager tests
│   ├── test_connection.py   # Connection manager tests
│   └── test_main.py         # API endpoint tests
├── docs/
│   ├── plans/               # Design and implementation plans
│   └── TESTING.md           # Manual testing guide
├── requirements.txt
├── pyproject.toml
└── run.py
```

## License

[Add your license here]
