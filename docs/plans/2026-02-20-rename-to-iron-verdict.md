# Rename judgeme → Iron Verdict Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace all `judgeme`/`JudgeMe` identifiers with `iron_verdict`/`Iron Verdict` across the codebase.

**Architecture:** Three-layer rename — package structure first (directory + pyproject.toml), then all code references (imports, loggers, titles, Alpine function), then docs. Tests run after layer 2 as the main verification gate. Each layer committed separately.

**Tech Stack:** Python (setuptools packaging), FastAPI, Alpine.js

---

### Task 1: Create worktree

**Files:** none

**Step 1: Create the worktree and branch**

```bash
git -C "c:/Users/alexa/OneDrive/Dokumente/00_projects/judgeme" worktree add .worktrees/rename-iron-verdict -b feature/rename-iron-verdict
```

**Step 2: Reinstall the editable package pointing at the worktree**

```bash
"c:/Users/alexa/OneDrive/Dokumente/00_projects/judgeme/.venv/Scripts/pip.exe" install -e "c:/Users/alexa/OneDrive/Dokumente/00_projects/judgeme/.worktrees/rename-iron-verdict"
```

Expected: `Successfully installed judgeme-0.1.0`

---

### Task 2: Rename the package directory

**Files:**
- Rename: `src/judgeme/` → `src/iron_verdict/`

**Step 1: Rename with git mv (preserves history)**

```bash
git -C "c:/Users/alexa/OneDrive/Dokumente/00_projects/judgeme/.worktrees/rename-iron-verdict" mv src/judgeme src/iron_verdict
```

**Step 2: Verify**

```bash
ls "c:/Users/alexa/OneDrive/Dokumente/00_projects/judgeme/.worktrees/rename-iron-verdict/src/"
```

Expected: only `iron_verdict/` visible (no `judgeme/`).

---

### Task 3: Update pyproject.toml

**Files:**
- Modify: `pyproject.toml:6`

**Step 1: Edit**

Change line 6 from:
```toml
name = "judgeme"
```
to:
```toml
name = "iron-verdict"
```

---

### Task 4: Update run.py

**Files:**
- Modify: `run.py:7,13`

**Step 1: Edit**

Change:
```python
from judgeme.config import settings
```
to:
```python
from iron_verdict.config import settings
```

Change:
```python
        "judgeme.main:app",
```
to:
```python
        "iron_verdict.main:app",
```

---

### Task 5: Update src/iron_verdict/main.py imports and identifiers

**Files:**
- Modify: `src/iron_verdict/main.py:5,6,7,20,22,90`

**Step 1: Update imports (lines 5–7, 20)**

Change:
```python
from judgeme.config import settings
from judgeme.session import SessionManager
from judgeme.connection import ConnectionManager
```
to:
```python
from iron_verdict.config import settings
from iron_verdict.session import SessionManager
from iron_verdict.connection import ConnectionManager
```

And line 20:
```python
from judgeme.logging_config import setup_logging
```
to:
```python
from iron_verdict.logging_config import setup_logging
```

**Step 2: Update logger namespace (line 22)**

Change:
```python
logger = logging.getLogger("judgeme")
```
to:
```python
logger = logging.getLogger("iron_verdict")
```

**Step 3: Update FastAPI title (line 90)**

Change:
```python
app = FastAPI(title="JudgeMe", lifespan=lifespan)
```
to:
```python
app = FastAPI(title="Iron Verdict", lifespan=lifespan)
```

---

### Task 6: Update logger namespaces in connection.py and logging_config.py

**Files:**
- Modify: `src/iron_verdict/connection.py:6`
- Modify: `src/iron_verdict/logging_config.py:26`

**Step 1: connection.py**

Change:
```python
logger = logging.getLogger("judgeme")
```
to:
```python
logger = logging.getLogger("iron_verdict")
```

**Step 2: logging_config.py**

Change:
```python
logger = logging.getLogger("judgeme")
```
to:
```python
logger = logging.getLogger("iron_verdict")
```

---

### Task 7: Update test imports

**Files:**
- Modify: `tests/test_session.py:2`
- Modify: `tests/test_connection.py:4`
- Modify: `tests/test_main.py:9,10,17`
- Modify: `tests/test_logging_config.py:3`

**Step 1: test_session.py**

Change:
```python
from judgeme.session import SessionManager
```
to:
```python
from iron_verdict.session import SessionManager
```

**Step 2: test_connection.py**

Change:
```python
from judgeme.connection import ConnectionManager
```
to:
```python
from iron_verdict.connection import ConnectionManager
```

**Step 3: test_main.py (3 occurrences)**

Change:
```python
from judgeme.main import app, session_manager
from judgeme.config import settings
```
to:
```python
from iron_verdict.main import app, session_manager
from iron_verdict.config import settings
```

And line 17:
```python
        from judgeme.main import limiter
```
to:
```python
        from iron_verdict.main import limiter
```

**Step 4: test_logging_config.py**

Change:
```python
from judgeme.logging_config import JsonFormatter
```
to:
```python
from iron_verdict.logging_config import JsonFormatter
```

---

### Task 8: Update Alpine.js function name in index.html

**Files:**
- Modify: `src/iron_verdict/static/index.html:682,908`

**Step 1: Update x-data attribute (line 682)**

Change:
```html
<div x-data="judgemeApp()">
```
to:
```html
<div x-data="ironVerdictApp()">
```

**Step 2: Update function definition (line 908)**

Change:
```javascript
        function judgemeApp() {
```
to:
```javascript
        function ironVerdictApp() {
```

---

### Task 9: Reinstall package and run tests

**Step 1: Reinstall the package (picks up new package name)**

```bash
"c:/Users/alexa/OneDrive/Dokumente/00_projects/judgeme/.venv/Scripts/pip.exe" install -e "c:/Users/alexa/OneDrive/Dokumente/00_projects/judgeme/.worktrees/rename-iron-verdict"
```

Expected: `Successfully installed iron-verdict-0.1.0`

**Step 2: Run tests**

```bash
"c:/Users/alexa/OneDrive/Dokumente/00_projects/judgeme/.venv/Scripts/python.exe" -m pytest "c:/Users/alexa/OneDrive/Dokumente/00_projects/judgeme/.worktrees/rename-iron-verdict/tests/" -q --tb=short
```

Expected: all tests pass, no import errors.

**Step 3: Commit layers 1 and 2**

```bash
git -C "c:/Users/alexa/OneDrive/Dokumente/00_projects/judgeme/.worktrees/rename-iron-verdict" add -A
git -C "c:/Users/alexa/OneDrive/Dokumente/00_projects/judgeme/.worktrees/rename-iron-verdict" commit -m "refactor: rename judgeme package to iron_verdict"
```

---

### Task 10: Update README.md

**Files:**
- Modify: `README.md:1,3`

**Step 1: Edit**

Change:
```markdown
# JudgeMe

A real-time powerlifting competition judging application.
```
to:
```markdown
# Iron Verdict

A real-time powerlifting competition judging application.
```

**Step 2: Commit**

```bash
git -C "c:/Users/alexa/OneDrive/Dokumente/00_projects/judgeme/.worktrees/rename-iron-verdict" add README.md
git -C "c:/Users/alexa/OneDrive/Dokumente/00_projects/judgeme/.worktrees/rename-iron-verdict" commit -m "docs: rename JudgeMe to Iron Verdict in README"
```

---

### Task 11: Verify no remaining judgeme references

**Step 1: Search for any missed occurrences**

```bash
grep -ri "judgeme" "c:/Users/alexa/OneDrive/Dokumente/00_projects/judgeme/.worktrees/rename-iron-verdict/src" "c:/Users/alexa/OneDrive/Dokumente/00_projects/judgeme/.worktrees/rename-iron-verdict/tests" "c:/Users/alexa/OneDrive/Dokumente/00_projects/judgeme/.worktrees/rename-iron-verdict/run.py" "c:/Users/alexa/OneDrive/Dokumente/00_projects/judgeme/.worktrees/rename-iron-verdict/README.md" "c:/Users/alexa/OneDrive/Dokumente/00_projects/judgeme/.worktrees/rename-iron-verdict/pyproject.toml"
```

Expected: no output (zero matches).

If any remain, fix them and amend the relevant commit.
