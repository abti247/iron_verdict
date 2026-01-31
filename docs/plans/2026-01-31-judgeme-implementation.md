# JudgeMe Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a real-time powerlifting judging web app with FastAPI + WebSockets + Alpine.js

**Architecture:** In-memory session-based system. 3 judges + 1 display join sessions via 6-char codes. WebSockets broadcast votes/timer/state. No database, ephemeral sessions with activity-based expiration.

**Tech Stack:** FastAPI, WebSockets, Alpine.js, pytest, uvicorn

---

## Task 1: Project Setup & Dependencies

**Files:**
- Create: `requirements.txt`
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `src/judgeme/__init__.py`
- Create: `tests/__init__.py`

**Step 1: Create project structure**

```bash
mkdir -p src/judgeme tests
touch src/judgeme/__init__.py tests/__init__.py
```

**Step 2: Write requirements.txt**

Create `requirements.txt`:
```
fastapi==0.115.0
uvicorn[standard]==0.32.0
pytest==8.3.4
pytest-asyncio==0.24.0
python-dotenv==1.0.1
```

**Step 3: Write pyproject.toml**

Create `pyproject.toml`:
```toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "judgeme"
version = "0.1.0"
description = "Powerlifting competition judging application"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.4",
    "pytest-asyncio>=0.24.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

**Step 4: Write .gitignore**

Create `.gitignore`:
```
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
env/
.venv
*.egg-info/
dist/
build/
.pytest_cache/
.coverage
htmlcov/
.env
.DS_Store
```

**Step 5: Install dependencies**

Run: `pip install -r requirements.txt`
Expected: All packages install successfully

**Step 6: Commit**

```bash
git add requirements.txt pyproject.toml .gitignore src/ tests/
git commit -m "chore: initialize project structure and dependencies"
```

---

## Task 2: Session Manager - Generate Codes

**Files:**
- Create: `src/judgeme/session.py`
- Create: `tests/test_session.py`

**Step 1: Write failing test for session code generation**

Create `tests/test_session.py`:
```python
from judgeme.session import SessionManager


def test_generate_session_code_creates_6_char_code():
    manager = SessionManager()
    code = manager.generate_session_code()
    assert len(code) == 6
    assert code.isalnum()


def test_generate_session_code_creates_unique_codes():
    manager = SessionManager()
    code1 = manager.generate_session_code()
    code2 = manager.generate_session_code()
    assert code1 != code2
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_session.py -v`
Expected: FAIL - SessionManager not defined

**Step 3: Write minimal implementation**

Create `src/judgeme/session.py`:
```python
import random
import string


class SessionManager:
    def __init__(self):
        self.sessions = {}

    def generate_session_code(self) -> str:
        """Generate a unique 6-character alphanumeric session code."""
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            if code not in self.sessions:
                return code
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_session.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/judgeme/session.py tests/test_session.py
git commit -m "feat: add session code generation"
```

---

## Task 3: Session Manager - Create Session

**Files:**
- Modify: `src/judgeme/session.py`
- Modify: `tests/test_session.py`

**Step 1: Write failing test for create_session**

Add to `tests/test_session.py`:
```python
from datetime import datetime


def test_create_session_returns_code():
    manager = SessionManager()
    code = manager.create_session()
    assert len(code) == 6
    assert code in manager.sessions


def test_create_session_initializes_structure():
    manager = SessionManager()
    code = manager.create_session()
    session = manager.sessions[code]

    assert "judges" in session
    assert "left" in session["judges"]
    assert "center" in session["judges"]
    assert "right" in session["judges"]
    assert "displays" in session
    assert session["state"] == "waiting"
    assert session["timer_state"] == "idle"
    assert "last_activity" in session
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_session.py::test_create_session_returns_code -v`
Expected: FAIL - create_session method not defined

**Step 3: Write implementation**

Modify `src/judgeme/session.py`:
```python
import random
import string
from datetime import datetime
from typing import Dict, Any


class SessionManager:
    def __init__(self):
        self.sessions: Dict[str, Dict[str, Any]] = {}

    def generate_session_code(self) -> str:
        """Generate a unique 6-character alphanumeric session code."""
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            if code not in self.sessions:
                return code

    def create_session(self) -> str:
        """Create a new session and return its code."""
        code = self.generate_session_code()
        self.sessions[code] = {
            "judges": {
                "left": {
                    "connected": False,
                    "is_head": False,
                    "current_vote": None,
                    "locked": False,
                },
                "center": {
                    "connected": False,
                    "is_head": True,
                    "current_vote": None,
                    "locked": False,
                },
                "right": {
                    "connected": False,
                    "is_head": False,
                    "current_vote": None,
                    "locked": False,
                },
            },
            "displays": [],
            "state": "waiting",
            "timer_state": "idle",
            "last_activity": datetime.now(),
        }
        return code
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_session.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/judgeme/session.py tests/test_session.py
git commit -m "feat: add session creation with initial state"
```

---

## Task 4: Session Manager - Join Session

**Files:**
- Modify: `src/judgeme/session.py`
- Modify: `tests/test_session.py`

**Step 1: Write failing tests for join_session**

Add to `tests/test_session.py`:
```python
def test_join_session_as_judge_succeeds():
    manager = SessionManager()
    code = manager.create_session()

    result = manager.join_session(code, "left_judge")
    assert result["success"] is True
    assert manager.sessions[code]["judges"]["left"]["connected"] is True


def test_join_session_invalid_code_fails():
    manager = SessionManager()
    result = manager.join_session("INVALID", "left_judge")
    assert result["success"] is False
    assert "Session not found" in result["error"]


def test_join_session_role_already_taken_fails():
    manager = SessionManager()
    code = manager.create_session()
    manager.join_session(code, "left_judge")

    result = manager.join_session(code, "left_judge")
    assert result["success"] is False
    assert "already taken" in result["error"]


def test_join_session_as_display_succeeds():
    manager = SessionManager()
    code = manager.create_session()

    result = manager.join_session(code, "display")
    assert result["success"] is True
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_session.py::test_join_session_as_judge_succeeds -v`
Expected: FAIL - join_session not defined

**Step 3: Write implementation**

Modify `src/judgeme/session.py`, add method to SessionManager class:
```python
    def join_session(self, code: str, role: str) -> Dict[str, Any]:
        """
        Join a session with specified role.

        Args:
            code: Session code
            role: One of "left_judge", "center_judge", "right_judge", "display"

        Returns:
            Dict with success status and error message if failed
        """
        if code not in self.sessions:
            return {"success": False, "error": "Session not found"}

        session = self.sessions[code]

        if role == "display":
            return {"success": True, "is_head": False}

        # Parse judge role
        position = role.replace("_judge", "")
        if position not in ["left", "center", "right"]:
            return {"success": False, "error": "Invalid role"}

        judge = session["judges"][position]
        if judge["connected"]:
            return {"success": False, "error": "Role already taken"}

        judge["connected"] = True
        is_head = judge["is_head"]

        return {"success": True, "is_head": is_head}
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_session.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/judgeme/session.py tests/test_session.py
git commit -m "feat: add session join with role validation"
```

---

## Task 5: Session Manager - Vote Locking Logic

**Files:**
- Modify: `src/judgeme/session.py`
- Modify: `tests/test_session.py`

**Step 1: Write failing tests for lock_vote**

Add to `tests/test_session.py`:
```python
def test_lock_vote_succeeds():
    manager = SessionManager()
    code = manager.create_session()
    manager.join_session(code, "left_judge")

    result = manager.lock_vote(code, "left", "white")
    assert result["success"] is True
    assert manager.sessions[code]["judges"]["left"]["current_vote"] == "white"
    assert manager.sessions[code]["judges"]["left"]["locked"] is True


def test_lock_vote_invalid_session_fails():
    manager = SessionManager()
    result = manager.lock_vote("INVALID", "left", "white")
    assert result["success"] is False


def test_lock_vote_updates_last_activity():
    manager = SessionManager()
    code = manager.create_session()
    manager.join_session(code, "left_judge")

    before = manager.sessions[code]["last_activity"]
    manager.lock_vote(code, "left", "red")
    after = manager.sessions[code]["last_activity"]

    assert after > before


def test_all_votes_locked_triggers_results():
    manager = SessionManager()
    code = manager.create_session()
    manager.join_session(code, "left_judge")
    manager.join_session(code, "center_judge")
    manager.join_session(code, "right_judge")

    manager.lock_vote(code, "left", "white")
    manager.lock_vote(code, "center", "red")
    result = manager.lock_vote(code, "right", "white")

    assert result["all_locked"] is True
    assert manager.sessions[code]["state"] == "showing_results"
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_session.py::test_lock_vote_succeeds -v`
Expected: FAIL - lock_vote not defined

**Step 3: Write implementation**

Modify `src/judgeme/session.py`, add method to SessionManager class:
```python
    def lock_vote(self, code: str, position: str, color: str) -> Dict[str, Any]:
        """
        Lock in a judge's vote.

        Args:
            code: Session code
            position: Judge position ("left", "center", "right")
            color: Vote color ("white", "red", "blue", "yellow")

        Returns:
            Dict with success status and all_locked flag
        """
        if code not in self.sessions:
            return {"success": False, "error": "Session not found"}

        session = self.sessions[code]
        judge = session["judges"][position]

        judge["current_vote"] = color
        judge["locked"] = True
        session["last_activity"] = datetime.now()

        # Check if all judges locked
        all_locked = all(
            j["locked"] for j in session["judges"].values() if j["connected"]
        )

        if all_locked:
            session["state"] = "showing_results"

        return {"success": True, "all_locked": all_locked}
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_session.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/judgeme/session.py tests/test_session.py
git commit -m "feat: add vote locking with state transition logic"
```

---

## Task 6: Session Manager - Reset for Next Lift

**Files:**
- Modify: `src/judgeme/session.py`
- Modify: `tests/test_session.py`

**Step 1: Write failing test for reset_for_next_lift**

Add to `tests/test_session.py`:
```python
def test_reset_for_next_lift_clears_votes():
    manager = SessionManager()
    code = manager.create_session()
    manager.join_session(code, "left_judge")
    manager.lock_vote(code, "left", "white")

    manager.reset_for_next_lift(code)

    session = manager.sessions[code]
    assert session["judges"]["left"]["current_vote"] is None
    assert session["judges"]["left"]["locked"] is False
    assert session["state"] == "waiting"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_session.py::test_reset_for_next_lift_clears_votes -v`
Expected: FAIL - reset_for_next_lift not defined

**Step 3: Write implementation**

Modify `src/judgeme/session.py`, add method to SessionManager class:
```python
    def reset_for_next_lift(self, code: str) -> Dict[str, Any]:
        """Reset session state for next lift."""
        if code not in self.sessions:
            return {"success": False, "error": "Session not found"}

        session = self.sessions[code]

        for judge in session["judges"].values():
            judge["current_vote"] = None
            judge["locked"] = False

        session["state"] = "waiting"

        return {"success": True}
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_session.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/judgeme/session.py tests/test_session.py
git commit -m "feat: add reset logic for next lift"
```

---

## Task 7: Session Manager - Activity Timeout & Cleanup

**Files:**
- Modify: `src/judgeme/session.py`
- Modify: `tests/test_session.py`

**Step 1: Write failing tests for cleanup**

Add to `tests/test_session.py`:
```python
from datetime import timedelta


def test_get_expired_sessions_returns_old_sessions():
    manager = SessionManager()
    code = manager.create_session()

    # Manually set old timestamp
    manager.sessions[code]["last_activity"] = datetime.now() - timedelta(hours=5)

    expired = manager.get_expired_sessions(hours=4)
    assert code in expired


def test_delete_session_removes_from_memory():
    manager = SessionManager()
    code = manager.create_session()

    manager.delete_session(code)
    assert code not in manager.sessions
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_session.py::test_get_expired_sessions_returns_old_sessions -v`
Expected: FAIL - get_expired_sessions not defined

**Step 3: Write implementation**

Modify `src/judgeme/session.py`, add imports and methods:
```python
from datetime import datetime, timedelta
from typing import Dict, Any, List

# Add to SessionManager class:
    def get_expired_sessions(self, hours: int = 4) -> List[str]:
        """Get list of session codes that have expired."""
        cutoff = datetime.now() - timedelta(hours=hours)
        expired = []

        for code, session in self.sessions.items():
            if session["last_activity"] < cutoff:
                expired.append(code)

        return expired

    def delete_session(self, code: str) -> None:
        """Delete a session from memory."""
        if code in self.sessions:
            del self.sessions[code]
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_session.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/judgeme/session.py tests/test_session.py
git commit -m "feat: add session expiration and cleanup logic"
```

---

## Task 8: FastAPI Application Setup

**Files:**
- Create: `src/judgeme/main.py`
- Create: `tests/test_main.py`

**Step 1: Write basic FastAPI app**

Create `src/judgeme/main.py`:
```python
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from judgeme.session import SessionManager

app = FastAPI(title="JudgeMe")
session_manager = SessionManager()


@app.get("/")
async def root():
    return {"message": "JudgeMe API"}


@app.post("/api/sessions")
async def create_session():
    """Create a new judging session."""
    code = session_manager.create_session()
    return {"session_code": code}
```

**Step 2: Write test for create session endpoint**

Create `tests/test_main.py`:
```python
from fastapi.testclient import TestClient
from judgeme.main import app

client = TestClient(app)


def test_create_session_returns_code():
    response = client.post("/api/sessions")
    assert response.status_code == 200
    data = response.json()
    assert "session_code" in data
    assert len(data["session_code"]) == 6
```

**Step 3: Run test to verify it passes**

Run: `pytest tests/test_main.py -v`
Expected: PASS

**Step 4: Test manually**

Run: `uvicorn judgeme.main:app --reload`
Visit: http://localhost:8000
Expected: See {"message": "JudgeMe API"}

Stop server: Ctrl+C

**Step 5: Commit**

```bash
git add src/judgeme/main.py tests/test_main.py
git commit -m "feat: add FastAPI app with session creation endpoint"
```

---

## Task 9: WebSocket Connection Manager

**Files:**
- Create: `src/judgeme/connection.py`
- Create: `tests/test_connection.py`

**Step 1: Write failing test for ConnectionManager**

Create `tests/test_connection.py`:
```python
import pytest
from judgeme.connection import ConnectionManager


@pytest.mark.asyncio
async def test_add_connection():
    manager = ConnectionManager()
    mock_ws = "mock_websocket"

    manager.add_connection("ABC123", "left_judge", mock_ws)

    assert "ABC123" in manager.active_connections
    assert "left_judge" in manager.active_connections["ABC123"]


@pytest.mark.asyncio
async def test_remove_connection():
    manager = ConnectionManager()
    mock_ws = "mock_websocket"

    manager.add_connection("ABC123", "left_judge", mock_ws)
    manager.remove_connection("ABC123", "left_judge")

    assert "left_judge" not in manager.active_connections.get("ABC123", {})
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_connection.py -v`
Expected: FAIL - ConnectionManager not defined

**Step 3: Write implementation**

Create `src/judgeme/connection.py`:
```python
from typing import Dict, Any
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        # Structure: {session_code: {role: websocket}}
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}

    def add_connection(self, session_code: str, role: str, websocket: WebSocket):
        """Add a WebSocket connection to a session."""
        if session_code not in self.active_connections:
            self.active_connections[session_code] = {}
        self.active_connections[session_code][role] = websocket

    def remove_connection(self, session_code: str, role: str):
        """Remove a WebSocket connection from a session."""
        if session_code in self.active_connections:
            self.active_connections[session_code].pop(role, None)
            if not self.active_connections[session_code]:
                del self.active_connections[session_code]

    async def broadcast_to_session(self, session_code: str, message: Dict[str, Any]):
        """Broadcast a message to all connections in a session."""
        if session_code not in self.active_connections:
            return

        for websocket in self.active_connections[session_code].values():
            await websocket.send_json(message)

    async def send_to_role(self, session_code: str, role: str, message: Dict[str, Any]):
        """Send a message to a specific role in a session."""
        if session_code in self.active_connections:
            websocket = self.active_connections[session_code].get(role)
            if websocket:
                await websocket.send_json(message)
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_connection.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/judgeme/connection.py tests/test_connection.py
git commit -m "feat: add WebSocket connection manager"
```

---

## Task 10: WebSocket Endpoint - Join Session

**Files:**
- Modify: `src/judgeme/main.py`

**Step 1: Add WebSocket endpoint for joining**

Modify `src/judgeme/main.py`:
```python
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from judgeme.session import SessionManager
from judgeme.connection import ConnectionManager
import json

app = FastAPI(title="JudgeMe")
session_manager = SessionManager()
connection_manager = ConnectionManager()


@app.get("/")
async def root():
    return {"message": "JudgeMe API"}


@app.post("/api/sessions")
async def create_session():
    """Create a new judging session."""
    code = session_manager.create_session()
    return {"session_code": code}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time communication."""
    await websocket.accept()

    session_code = None
    role = None

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if message["type"] == "join":
                session_code = message["session_code"]
                role = message["role"]

                # Validate join
                result = session_manager.join_session(session_code, role)

                if not result["success"]:
                    await websocket.send_json({
                        "type": "join_error",
                        "message": result["error"]
                    })
                    await websocket.close()
                    return

                # Add connection
                connection_manager.add_connection(session_code, role, websocket)

                # Send success
                await websocket.send_json({
                    "type": "join_success",
                    "role": role,
                    "is_head": result["is_head"],
                    "session_state": session_manager.sessions[session_code]
                })

    except WebSocketDisconnect:
        if session_code and role:
            connection_manager.remove_connection(session_code, role)
            # Update session state if judge disconnected
            if role.endswith("_judge"):
                position = role.replace("_judge", "")
                if session_code in session_manager.sessions:
                    session_manager.sessions[session_code]["judges"][position]["connected"] = False
```

**Step 2: Test manually with a WebSocket client**

Run: `uvicorn judgeme.main:app --reload`

Use browser console or wscat to test:
```javascript
const ws = new WebSocket('ws://localhost:8000/ws');
ws.onopen = () => ws.send(JSON.stringify({type: 'join', session_code: 'TEST01', role: 'left_judge'}));
ws.onmessage = (e) => console.log(JSON.parse(e.data));
```

Expected: Receive join_error (session not found) or join_success

Stop server: Ctrl+C

**Step 3: Commit**

```bash
git add src/judgeme/main.py
git commit -m "feat: add WebSocket join session logic"
```

---

## Task 11: WebSocket Endpoint - Vote Lock

**Files:**
- Modify: `src/judgeme/main.py`

**Step 1: Add vote_lock message handling**

Modify `src/judgeme/main.py`, add to the websocket_endpoint while loop after join handling:
```python
            elif message["type"] == "vote_lock":
                if not session_code or not role:
                    continue

                position = role.replace("_judge", "")
                color = message["color"]

                result = session_manager.lock_vote(session_code, position, color)

                if result["success"]:
                    # Notify display that a judge voted (no color)
                    await connection_manager.send_to_role(
                        session_code,
                        "display",
                        {"type": "judge_voted", "position": position}
                    )

                    # If all locked, broadcast results
                    if result.get("all_locked"):
                        votes = {
                            pos: judge["current_vote"]
                            for pos, judge in session_manager.sessions[session_code]["judges"].items()
                            if judge["connected"]
                        }
                        await connection_manager.broadcast_to_session(
                            session_code,
                            {"type": "show_results", "votes": votes}
                        )
```

**Step 2: Test manually**

Run: `uvicorn judgeme.main:app --reload`

Create session via POST to /api/sessions, then use WebSocket to join and vote.

Stop server: Ctrl+C

**Step 3: Commit**

```bash
git add src/judgeme/main.py
git commit -m "feat: add vote lock WebSocket message handling"
```

---

## Task 12: WebSocket Endpoint - Timer Controls

**Files:**
- Modify: `src/judgeme/main.py`

**Step 1: Add timer message handling**

Modify `src/judgeme/main.py`, add to websocket_endpoint while loop:
```python
            elif message["type"] == "timer_start":
                if not session_code:
                    continue

                import time
                await connection_manager.broadcast_to_session(
                    session_code,
                    {
                        "type": "timer_start",
                        "server_timestamp": time.time()
                    }
                )

            elif message["type"] == "timer_reset":
                if not session_code:
                    continue

                await connection_manager.broadcast_to_session(
                    session_code,
                    {"type": "timer_reset"}
                )
```

**Step 2: Test manually**

Run: `uvicorn judgeme.main:app --reload`

Test timer_start and timer_reset messages via WebSocket.

Stop server: Ctrl+C

**Step 3: Commit**

```bash
git add src/judgeme/main.py
git commit -m "feat: add timer control WebSocket messages"
```

---

## Task 13: WebSocket Endpoint - Next Lift & End Session

**Files:**
- Modify: `src/judgeme/main.py`

**Step 1: Add next_lift and end_session handling**

Modify `src/judgeme/main.py`, add to websocket_endpoint while loop:
```python
            elif message["type"] == "next_lift":
                if not session_code:
                    continue

                session_manager.reset_for_next_lift(session_code)
                await connection_manager.broadcast_to_session(
                    session_code,
                    {"type": "reset_for_next_lift"}
                )

            elif message["type"] == "end_session_confirmed":
                if not session_code:
                    continue

                await connection_manager.broadcast_to_session(
                    session_code,
                    {"type": "session_ended", "reason": "head_judge"}
                )

                session_manager.delete_session(session_code)

                # Close all connections
                if session_code in connection_manager.active_connections:
                    for ws in connection_manager.active_connections[session_code].values():
                        await ws.close()
```

**Step 2: Test manually**

Run: `uvicorn judgeme.main:app --reload`

Test next_lift and end_session_confirmed via WebSocket.

Stop server: Ctrl+C

**Step 3: Commit**

```bash
git add src/judgeme/main.py
git commit -m "feat: add next lift and end session WebSocket messages"
```

---

## Task 14: Frontend - Base HTML Template

**Files:**
- Create: `src/judgeme/static/index.html`
- Modify: `src/judgeme/main.py`

**Step 1: Create static directory and index.html**

```bash
mkdir -p src/judgeme/static
```

Create `src/judgeme/static/index.html`:
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>JudgeMe - Powerlifting Judging</title>
    <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: system-ui, -apple-system, sans-serif; padding: 20px; }
        .container { max-width: 600px; margin: 0 auto; }
        button { padding: 12px 24px; font-size: 16px; cursor: pointer; border: none; border-radius: 4px; }
        button:disabled { opacity: 0.5; cursor: not-allowed; }
        input { padding: 12px; font-size: 16px; border: 1px solid #ccc; border-radius: 4px; width: 100%; }
        .hidden { display: none; }
    </style>
</head>
<body>
    <div class="container" x-data="judgemeApp()">
        <h1>JudgeMe</h1>

        <!-- Landing screen -->
        <div x-show="screen === 'landing'">
            <h2>Welcome</h2>
            <button @click="createSession()">Create New Session</button>
            <p>or</p>
            <input type="text" x-model="joinCode" placeholder="Enter session code">
            <button @click="screen = 'role-select'">Join Session</button>
        </div>

        <!-- Role selection screen -->
        <div x-show="screen === 'role-select'" class="hidden">
            <h2>Select Your Role</h2>
            <p>Session: <span x-text="sessionCode"></span></p>
            <button @click="joinSession('left_judge')">Left Judge</button>
            <button @click="joinSession('center_judge')">Center Judge (Head)</button>
            <button @click="joinSession('right_judge')">Right Judge</button>
            <button @click="joinSession('display')">Display</button>
        </div>

        <!-- Judge screen placeholder -->
        <div x-show="screen === 'judge'" class="hidden">
            <h2>Judge Interface</h2>
            <p>Role: <span x-text="role"></span></p>
            <p>Connected!</p>
        </div>

        <!-- Display screen placeholder -->
        <div x-show="screen === 'display'" class="hidden">
            <h2>Display Screen</h2>
            <p>Session: <span x-text="sessionCode"></span></p>
        </div>
    </div>

    <script>
        function judgemeApp() {
            return {
                screen: 'landing',
                sessionCode: '',
                joinCode: '',
                role: '',
                ws: null,

                async createSession() {
                    const response = await fetch('/api/sessions', { method: 'POST' });
                    const data = await response.json();
                    this.sessionCode = data.session_code;
                    this.screen = 'role-select';
                },

                joinSession(role) {
                    this.role = role;
                    const code = this.sessionCode || this.joinCode;
                    this.sessionCode = code;

                    this.ws = new WebSocket(`ws://${window.location.host}/ws`);

                    this.ws.onopen = () => {
                        this.ws.send(JSON.stringify({
                            type: 'join',
                            session_code: code,
                            role: role
                        }));
                    };

                    this.ws.onmessage = (event) => {
                        const message = JSON.parse(event.data);
                        if (message.type === 'join_success') {
                            this.screen = role === 'display' ? 'display' : 'judge';
                        } else if (message.type === 'join_error') {
                            alert(message.message);
                        }
                    };
                }
            };
        }
    </script>
</body>
</html>
```

**Step 2: Serve static files from FastAPI**

Modify `src/judgeme/main.py`:
```python
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from judgeme.session import SessionManager
from judgeme.connection import ConnectionManager
import json
import os

app = FastAPI(title="JudgeMe")
session_manager = SessionManager()
connection_manager = ConnectionManager()

# Serve static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main HTML page."""
    with open(os.path.join(static_dir, "index.html")) as f:
        return f.read()

# ... rest of the code remains the same
```

**Step 3: Test manually**

Run: `uvicorn judgeme.main:app --reload`
Visit: http://localhost:8000
Expected: See landing page, create session, select role

Stop server: Ctrl+C

**Step 4: Commit**

```bash
git add src/judgeme/static/index.html src/judgeme/main.py
git commit -m "feat: add base HTML template with Alpine.js"
```

---

## Task 15: Frontend - Judge Voting Interface

**Files:**
- Modify: `src/judgeme/static/index.html`

**Step 1: Expand judge interface HTML**

Modify `src/judgeme/static/index.html`, replace the judge screen div:
```html
        <!-- Judge screen -->
        <div x-show="screen === 'judge'" class="hidden">
            <div style="background: #f5f5f5; padding: 10px; margin-bottom: 20px;">
                <strong>Session:</strong> <span x-text="sessionCode"></span> |
                <strong>Timer:</strong> <span x-text="timerDisplay" :style="timerExpired ? 'color: red;' : ''"></span>
            </div>

            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 20px;">
                <button
                    @click="selectVote('white')"
                    :disabled="voteLocked"
                    :style="selectedVote === 'white' ? 'background: white; border: 3px solid black;' : 'background: #f0f0f0;'">
                    White
                </button>
                <button
                    @click="selectVote('red')"
                    :disabled="voteLocked"
                    :style="selectedVote === 'red' ? 'background: #ff4444; color: white; border: 3px solid black;' : 'background: #ffcccc;'">
                    Red
                </button>
                <button
                    @click="selectVote('blue')"
                    :disabled="voteLocked"
                    :style="selectedVote === 'blue' ? 'background: #4444ff; color: white; border: 3px solid black;' : 'background: #ccccff;'">
                    Blue
                </button>
                <button
                    @click="selectVote('yellow')"
                    :disabled="voteLocked"
                    :style="selectedVote === 'yellow' ? 'background: #ffff44; border: 3px solid black;' : 'background: #ffffcc;'">
                    Yellow
                </button>
            </div>

            <button
                x-show="selectedVote && !voteLocked"
                @click="lockVote()"
                style="background: #28a745; color: white; width: 100%;">
                Lock In
            </button>

            <div x-show="voteLocked" style="margin-top: 20px; padding: 10px; background: #d4edda; border-radius: 4px;">
                Your vote: <strong x-text="selectedVote"></strong> (locked)
            </div>

            <!-- Head judge controls -->
            <div x-show="isHead" style="margin-top: 30px; border-top: 2px solid #ccc; padding-top: 20px;">
                <h3>Head Judge Controls</h3>
                <button @click="startTimer()" style="background: #007bff; color: white;">Start Timer</button>
                <button @click="resetTimer()" style="background: #6c757d; color: white;">Reset Timer</button>
                <button @click="nextLift()" :disabled="!resultsShown" style="background: #ffc107;">Next Lift</button>
                <button @click="confirmEndSession()" style="background: #dc3545; color: white;">End Session</button>
            </div>
        </div>
```

**Step 2: Add voting logic to Alpine.js**

Modify the `judgemeApp()` function in `src/judgeme/static/index.html`:
```javascript
        function judgemeApp() {
            return {
                screen: 'landing',
                sessionCode: '',
                joinCode: '',
                role: '',
                isHead: false,
                ws: null,
                selectedVote: null,
                voteLocked: false,
                resultsShown: false,
                timerDisplay: '60',
                timerExpired: false,
                timerInterval: null,

                async createSession() {
                    const response = await fetch('/api/sessions', { method: 'POST' });
                    const data = await response.json();
                    this.sessionCode = data.session_code;
                    this.screen = 'role-select';
                },

                joinSession(role) {
                    this.role = role;
                    const code = this.sessionCode || this.joinCode;
                    this.sessionCode = code;

                    this.ws = new WebSocket(`ws://${window.location.host}/ws`);

                    this.ws.onopen = () => {
                        this.ws.send(JSON.stringify({
                            type: 'join',
                            session_code: code,
                            role: role
                        }));
                    };

                    this.ws.onmessage = (event) => {
                        const message = JSON.parse(event.data);
                        this.handleMessage(message);
                    };
                },

                handleMessage(message) {
                    if (message.type === 'join_success') {
                        this.isHead = message.is_head;
                        this.screen = this.role === 'display' ? 'display' : 'judge';
                    } else if (message.type === 'join_error') {
                        alert(message.message);
                    } else if (message.type === 'show_results') {
                        this.resultsShown = true;
                    } else if (message.type === 'reset_for_next_lift') {
                        this.resetVoting();
                    } else if (message.type === 'timer_start') {
                        this.startTimerCountdown(message.server_timestamp);
                    } else if (message.type === 'timer_reset') {
                        this.stopTimer();
                    } else if (message.type === 'session_ended') {
                        alert('Session ended');
                        this.ws.close();
                        this.screen = 'landing';
                    }
                },

                selectVote(color) {
                    if (!this.voteLocked) {
                        this.selectedVote = color;
                    }
                },

                lockVote() {
                    if (this.selectedVote && !this.voteLocked) {
                        this.voteLocked = true;
                        this.ws.send(JSON.stringify({
                            type: 'vote_lock',
                            color: this.selectedVote
                        }));
                    }
                },

                resetVoting() {
                    this.selectedVote = null;
                    this.voteLocked = false;
                    this.resultsShown = false;
                },

                startTimer() {
                    this.ws.send(JSON.stringify({ type: 'timer_start' }));
                },

                resetTimer() {
                    this.ws.send(JSON.stringify({ type: 'timer_reset' }));
                },

                startTimerCountdown(serverTimestamp) {
                    this.stopTimer();
                    const startTime = serverTimestamp * 1000;
                    const duration = 60000; // 60 seconds

                    this.timerInterval = setInterval(() => {
                        const elapsed = Date.now() - startTime;
                        const remaining = Math.max(0, duration - elapsed);
                        const seconds = Math.ceil(remaining / 1000);
                        this.timerDisplay = seconds;
                        this.timerExpired = seconds === 0;

                        if (seconds === 0) {
                            clearInterval(this.timerInterval);
                        }
                    }, 100);
                },

                stopTimer() {
                    if (this.timerInterval) {
                        clearInterval(this.timerInterval);
                    }
                    this.timerDisplay = '60';
                    this.timerExpired = false;
                },

                nextLift() {
                    this.ws.send(JSON.stringify({ type: 'next_lift' }));
                },

                confirmEndSession() {
                    if (confirm('Are you sure? This will disconnect all judges and the display')) {
                        this.ws.send(JSON.stringify({ type: 'end_session_confirmed' }));
                    }
                }
            };
        }
```

**Step 3: Test manually**

Run: `uvicorn judgeme.main:app --reload`
Open 3 tabs, create session, join as judges, test voting flow

Stop server: Ctrl+C

**Step 4: Commit**

```bash
git add src/judgeme/static/index.html
git commit -m "feat: add judge voting interface with Alpine.js logic"
```

---

## Task 16: Frontend - Display Interface

**Files:**
- Modify: `src/judgeme/static/index.html`

**Step 1: Expand display interface HTML**

Modify `src/judgeme/static/index.html`, replace the display screen div:
```html
        <!-- Display screen -->
        <div x-show="screen === 'display'" class="hidden">
            <div style="text-align: center; padding: 40px;">
                <h1 style="font-size: 48px; margin-bottom: 40px;"
                    :style="timerExpired ? 'color: red;' : ''"
                    x-text="timerDisplay">
                    60
                </h1>

                <div style="display: flex; justify-content: center; gap: 40px; margin-bottom: 40px;">
                    <!-- Left Judge -->
                    <div style="width: 120px; height: 120px; border-radius: 50%; border: 3px solid #ccc;"
                         :style="displayVotes.left ? `background: ${getVoteColor(displayVotes.left)};` : 'background: #f0f0f0;'">
                    </div>

                    <!-- Center Judge -->
                    <div style="width: 120px; height: 120px; border-radius: 50%; border: 3px solid #ccc;"
                         :style="displayVotes.center ? `background: ${getVoteColor(displayVotes.center)};` : 'background: #f0f0f0;'">
                    </div>

                    <!-- Right Judge -->
                    <div style="width: 120px; height: 120px; border-radius: 50%; border: 3px solid #ccc;"
                         :style="displayVotes.right ? `background: ${getVoteColor(displayVotes.right)};` : 'background: #f0f0f0;'">
                    </div>
                </div>

                <p style="font-size: 18px; color: #666;" x-text="displayStatus">Waiting for judges...</p>
            </div>
        </div>
```

**Step 2: Add display logic to Alpine.js**

Modify the `judgemeApp()` function, add these properties and methods:
```javascript
                displayVotes: { left: null, center: null, right: null },
                displayStatus: 'Waiting for judges...',

                // Add to handleMessage function:
                // } else if (message.type === 'show_results') {
                //     this.resultsShown = true;
                //     if (this.role === 'display') {
                //         this.displayVotes = message.votes;
                //         this.displayStatus = 'Results shown';
                //     }
                // } else if (message.type === 'reset_for_next_lift') {
                //     this.resetVoting();
                //     if (this.role === 'display') {
                //         this.displayVotes = { left: null, center: null, right: null };
                //         this.displayStatus = 'Waiting for judges...';
                //     }

                getVoteColor(vote) {
                    const colors = {
                        white: 'white',
                        red: '#ff4444',
                        blue: '#4444ff',
                        yellow: '#ffff44'
                    };
                    return colors[vote] || '#f0f0f0';
                }
```

**Step 3: Test manually**

Run: `uvicorn judgeme.main:app --reload`
Open 4 tabs: 3 judges + 1 display, test full voting flow

Stop server: Ctrl+C

**Step 4: Commit**

```bash
git add src/judgeme/static/index.html
git commit -m "feat: add display interface with three circular lights"
```

---

## Task 17: Multi-Tab Integration Test

**Files:**
- Create: `docs/TESTING.md`

**Step 1: Document manual testing procedure**

Create `docs/TESTING.md`:
```markdown
# JudgeMe Manual Testing Guide

## Multi-Tab Testing Procedure

### Setup
1. Start server: `uvicorn judgeme.main:app --reload`
2. Open 4 browser tabs/windows

### Test Flow

**Tab 1 - Left Judge:**
1. Click "Create New Session"
2. Note the session code (e.g., ABC123)
3. Click "Left Judge"
4. Verify: Timer shows 60, voting buttons enabled

**Tab 2 - Center Judge (Head):**
1. Enter session code from Tab 1
2. Click "Join Session"
3. Click "Center Judge (Head)"
4. Verify: Timer shows 60, voting buttons enabled, head judge controls visible

**Tab 3 - Right Judge:**
1. Enter session code
2. Click "Join Session"
3. Click "Right Judge"
4. Verify: Timer shows 60, voting buttons enabled

**Tab 4 - Display:**
1. Enter session code
2. Click "Join Session"
3. Click "Display"
4. Verify: Timer shows 60, three empty circles visible

### Test Timer (Tab 2 - Head Judge)
1. Click "Start Timer"
2. Verify all 4 tabs show countdown from 60
3. Wait for timer to reach 0
4. Verify timer turns red on all tabs
5. Click "Reset Timer"
6. Verify all tabs show 60 again

### Test Voting Flow
1. **Tab 1:** Click "White", then "Lock In"
   - Verify button disabled in Tab 1
2. **Tab 2:** Click "Red", then "Lock In"
   - Verify button disabled in Tab 2
3. **Tab 3:** Click "White", then "Lock In"
   - Verify button disabled in Tab 3
   - **All tabs:** Results appear simultaneously
   - **Tab 4:** Three circles fill with colors (White, Red, White)

### Test Next Lift (Tab 2 - Head Judge)
1. Click "Next Lift"
2. Verify all tabs:
   - Voting buttons re-enabled
   - Previous votes cleared
   - Display circles empty again

### Test End Session (Tab 2 - Head Judge)
1. Click "End Session"
2. Confirm dialog appears
3. Click OK
4. Verify all 4 tabs receive session ended message
5. Verify all tabs return to landing screen

## Edge Cases

### Role Already Taken
1. Open 2 tabs
2. Create session in Tab 1, join as Left Judge
3. In Tab 2, join same session, try to join as Left Judge
4. Verify: Error message "Role already taken"

### Invalid Session Code
1. Enter "XXXXXX" as session code
2. Try to join
3. Verify: Error message "Session not found"

### Judge Disconnection
1. Set up full session (3 judges + display)
2. Close one judge tab
3. Verify display shows disconnection (future feature)

## Success Criteria

- ✓ All 4 devices can join session
- ✓ Timer syncs across all devices
- ✓ Votes lock independently
- ✓ Results show simultaneously when all locked
- ✓ Head judge can advance to next lift
- ✓ Head judge can end session
- ✓ Role validation works
```

**Step 2: Perform manual test**

Run: `uvicorn judgeme.main:app --reload`
Follow the testing guide above
Document any bugs found

Stop server: Ctrl+C

**Step 3: Commit**

```bash
git add docs/TESTING.md
git commit -m "docs: add manual multi-tab testing guide"
```

---

## Task 18: Production Readiness - Environment Config

**Files:**
- Create: `.env.example`
- Create: `src/judgeme/config.py`

**Step 1: Create environment config example**

Create `.env.example`:
```
# Server Configuration
HOST=0.0.0.0
PORT=8000

# Session Configuration
SESSION_TIMEOUT_HOURS=4
```

**Step 2: Create config module**

Create `src/judgeme/config.py`:
```python
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    SESSION_TIMEOUT_HOURS: int = int(os.getenv("SESSION_TIMEOUT_HOURS", "4"))


settings = Settings()
```

**Step 3: Use config in main.py**

Modify `src/judgeme/main.py` to use settings:
```python
# At the top, add:
from judgeme.config import settings

# Keep rest of imports and code the same
```

**Step 4: Commit**

```bash
git add .env.example src/judgeme/config.py src/judgeme/main.py
git commit -m "feat: add environment configuration support"
```

---

## Task 19: Production Readiness - Run Script

**Files:**
- Create: `run.py`

**Step 1: Create run script**

Create `run.py`:
```python
#!/usr/bin/env python3
"""
JudgeMe application runner.
"""
import uvicorn
from judgeme.config import settings


if __name__ == "__main__":
    uvicorn.run(
        "judgeme.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True
    )
```

**Step 2: Make executable**

Run: `chmod +x run.py` (Unix/Mac) or skip on Windows

**Step 3: Test run script**

Run: `python run.py`
Visit: http://localhost:8000
Verify app works

Stop server: Ctrl+C

**Step 4: Commit**

```bash
git add run.py
git commit -m "feat: add application run script"
```

---

## Task 20: Documentation - README

**Files:**
- Modify: `README.md`

**Step 1: Write comprehensive README**

Modify `README.md`:
```markdown
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

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. (Optional) Create `.env` file:
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
```

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add comprehensive README with usage instructions"
```

---

## Task 21: Final Integration Test & Cleanup

**Files:**
- None (manual testing)

**Step 1: Run full integration test**

Run: `python run.py`

1. Open 4 browser tabs
2. Create session
3. Join as all 3 judges + display
4. Test complete flow:
   - Timer start/reset
   - All judges vote
   - Results display
   - Next lift
   - End session

Expected: Everything works end-to-end

Stop server: Ctrl+C

**Step 2: Run all automated tests**

Run: `pytest -v`
Expected: All tests PASS

**Step 3: Check code quality**

Run: `python -m py_compile src/judgeme/*.py`
Expected: No syntax errors

**Step 4: Final commit**

```bash
git add -A
git commit -m "chore: final integration test and cleanup"
```

---

## Implementation Complete

All tasks completed. The JudgeMe MVP is ready for use.

**Next Steps:**
- Deploy to a hosting service (Render, Railway, Heroku, etc.)
- Gather user feedback from real powerlifting meets
- Iterate based on feedback

**Future Enhancements (not in MVP):**
- Persistent session history
- Meet management (lifter tracking, flight organization)
- Mobile-optimized UI
- Audio signals for timer expiration
- Multiple concurrent sessions with better isolation
- Authentication for meet directors
