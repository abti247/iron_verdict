# Session Name Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a required session name to replace the join code on the display screen, so audience members can't see the join code.

**Architecture:** Name stored in session dict, returned in session_state on join. Display screen reads name from state; demo mode detects `?demo=` URL param and shows "DEMO" instead.

**Tech Stack:** FastAPI (Pydantic validation), Alpine.js frontend, pytest

---

### Task 1: session.py — create_session accepts name

**Files:**
- Modify: `src/judgeme/session.py:20-53`
- Test: `tests/test_session.py`

**Step 1: Write the failing test**

Add to `tests/test_session.py`:
```python
def test_create_session_stores_name():
    manager = SessionManager()
    code = manager.create_session("Platform A")
    assert manager.sessions[code]["name"] == "Platform A"
```

**Step 2: Run it to verify it fails**

Run: `pytest tests/test_session.py::test_create_session_stores_name -v`
Expected: `TypeError: create_session() takes 1 positional argument but 2 were given`

**Step 3: Update create_session signature and session dict**

In `src/judgeme/session.py`, change `create_session(self)` to `create_session(self, name: str)` and add `"name": name` to the session dict (after `"judges"`):

```python
def create_session(self, name: str) -> str:
    """Create a new session and return its code."""
    code = self.generate_session_code()
    self.sessions[code] = {
        "name": name,
        "judges": { ... },  # unchanged
        ...
    }
    return code
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_session.py::test_create_session_stores_name -v`
Expected: PASS

**Step 5: Fix all existing create_session() calls in tests**

Every call to `manager.create_session()` in `tests/test_session.py` needs a name arg. Replace all occurrences of `manager.create_session()` with `manager.create_session("Test")`. Also update the `session_code` fixture in `tests/test_main.py`:

```python
@pytest.fixture
def session_code():
    code = session_manager.create_session("Test Session")
    yield code
    if code in session_manager.sessions:
        session_manager.delete_session(code)
```

**Step 6: Run all tests**

Run: `pytest tests/ -v`
Expected: All 37+ tests pass

**Step 7: Commit**

```
git add src/judgeme/session.py tests/test_session.py tests/test_main.py
git commit -m "feat: create_session accepts required name parameter"
```

---

### Task 2: main.py — POST /api/sessions requires name in body

**Files:**
- Modify: `src/judgeme/main.py:1-33`
- Test: `tests/test_main.py`

**Step 1: Write failing tests**

Add to `tests/test_main.py`:
```python
def test_create_session_requires_name():
    response = client.post("/api/sessions", json={})
    assert response.status_code == 422

def test_create_session_rejects_empty_name():
    response = client.post("/api/sessions", json={"name": ""})
    assert response.status_code == 422

def test_create_session_rejects_whitespace_name():
    response = client.post("/api/sessions", json={"name": "   "})
    assert response.status_code == 422
```

Also update the existing test:
```python
def test_create_session_returns_code():
    response = client.post("/api/sessions", json={"name": "Test"})
    assert response.status_code == 200
    data = response.json()
    assert "session_code" in data
    assert len(data["session_code"]) == 6
```

**Step 2: Run to verify they fail**

Run: `pytest tests/test_main.py::test_create_session_requires_name tests/test_main.py::test_create_session_rejects_empty_name -v`
Expected: FAIL (endpoint currently returns 200 regardless)

**Step 3: Add Pydantic model and update endpoint**

In `src/judgeme/main.py`, add after imports:
```python
from pydantic import BaseModel, field_validator

class CreateSessionRequest(BaseModel):
    name: str

    @field_validator('name')
    @classmethod
    def name_not_empty(cls, v):
        if not v.strip():
            raise ValueError('name cannot be empty')
        return v.strip()
```

Update the endpoint:
```python
@app.post("/api/sessions")
async def create_session(request: CreateSessionRequest):
    """Create a new judging session."""
    code = session_manager.create_session(request.name)
    return {"session_code": code}
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_main.py -v`
Expected: All pass

**Step 5: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests pass

**Step 6: Commit**

```
git add src/judgeme/main.py tests/test_main.py
git commit -m "feat: POST /api/sessions requires non-empty name in body"
```

---

### Task 3: Frontend — name input, display header, demo indicator

**Files:**
- Modify: `src/judgeme/static/index.html`

No automated tests — verify manually by running the app.

**Step 1: Add sessionName and newSessionName to Alpine state**

In `judgemeApp()` return object (around line 782), add two fields:
```js
sessionName: '',
newSessionName: '',
isDemo: false,
```

**Step 2: Add name input to landing screen**

Replace the Create New Session button section (lines 620–623):
```html
<input type="text" placeholder="Session name (e.g. Platform A)" x-model="newSessionName">
<button class="btn-primary" @click="createSession()" :disabled="!newSessionName.trim()">
    Create New Session
</button>
```

**Step 3: Update createSession() to send name**

Replace `createSession()` (lines 806–820):
```js
async createSession() {
    try {
        const response = await fetch('/api/sessions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: this.newSessionName.trim() })
        });
        if (!response.ok) {
            alert('Failed to create session. Please try again.');
            return;
        }
        const data = await response.json();
        this.sessionCode = data.session_code;
        this.sessionName = this.newSessionName.trim();
        this.screen = 'role-select';
    } catch (error) {
        alert('Error creating session. Please check your connection.');
        console.error('Session creation error:', error);
    }
},
```

**Step 4: Extract sessionName from join_success**

In the `ws.onmessage` handler, find the `join_success` branch and add:
```js
this.sessionName = data.session_state?.name || '';
```
(Place it alongside the existing `this.isHead = data.is_head;` assignment.)

**Step 5: Update display header to show name (or DEMO)**

Replace line 728:
```html
<span class="session-code" @click="returnToRoleSelection()" x-text="sessionCode">ABC123</span>
```
with:
```html
<span x-show="!isDemo" style="font-family: var(--font-mono); color: var(--accent-primary); font-size: 20px;" x-text="sessionName"></span>
<span x-show="isDemo" style="font-family: var(--font-mono); color: var(--text-muted); font-size: 20px;">DEMO</span>
```

**Step 6: Set isDemo in init() and fix startDemo()**

In `init()`, after reading URL params (around line 1118), add:
```js
if (demoRole) {
    this.isDemo = true;
}
```

Update `startDemo()` (line 1083) to send a name:
```js
const response = await fetch('/api/sessions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: 'Demo' })
});
```

**Step 7: Manual verification**

Run the server: `uvicorn judgeme.main:app --reload`

Check:
- [ ] Landing screen shows name input; Create button disabled when empty
- [ ] After creating session, role-select screen still shows session code
- [ ] Display screen shows session name (not code)
- [ ] Start Demo: display window shows "DEMO" label
- [ ] Joining an existing session: display shows name from session state

**Step 8: Commit**

```
git add src/judgeme/static/index.html
git commit -m "feat: display screen shows session name; demo mode shows DEMO label"
```
