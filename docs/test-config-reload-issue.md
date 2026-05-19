# `importlib.reload()` + `from m import name` — Test-Isolation Foot-Gun

**Date:** 2026-05-19
**Status:** Two test patches landed on the VPortal branch as local workarounds; a proper fix is recommended but out of scope for that branch.

## TL;DR

The pattern `from iron_verdict.config import settings` is **fine** — it's standard Python and used throughout the codebase. The bug only surfaces when **one test reloads the `config` module** via `importlib.reload(cfg)` and **a later test in the same pytest process mutates an attribute** on the post-reload `Settings` instance. Other modules that imported `settings` before the reload still hold a reference to the **pre-reload** object and don't see the mutation.

We hit this twice on the VPortal branch — once in Task 3, once in Task 6. Patched both tests locally. The underlying defect is in [`tests/test_config.py`](../tests/test_config.py)'s use of `importlib.reload()`, not in the production import style.

## What `from m import name` actually does

```python
# iron_verdict/main.py — at import time
from iron_verdict.config import settings
```

After this line runs:

- `iron_verdict.config.settings` and `iron_verdict.main.settings` are **two names that point at the same object** — one `Settings` instance.
- They share a reference. Mutating an attribute through either name is visible through the other.

```python
config.settings.X = 5
assert main.settings.X == 5     # ✅ both names see the change (same object)
```

This is normal, idiomatic, and not the problem.

## What `importlib.reload(m)` does

```python
# tests/test_config.py
def reload_config():
    import iron_verdict.config as cfg
    importlib.reload(cfg)
    return cfg.settings
```

`importlib.reload(cfg)` **re-executes `iron_verdict/config.py` from top to bottom**, including:

```python
class Settings:
    HOST: str = os.getenv("HOST", "0.0.0.0")
    ...
    VPORTAL_FETCH_INTERVAL_MS: int = _read_fetch_interval()
    TEST_MODE: bool = os.getenv("TEST_MODE") == "1"
    ...

settings = Settings()           # ← runs again, creates a NEW instance
```

After reload:

- `iron_verdict.config.settings` now points at the **new** `Settings` instance.
- `iron_verdict.main.settings` still points at the **old** instance — Python doesn't re-execute the `from … import …` line in `main.py` when `config` is reloaded.
- Same for every other consumer: `vportal_proxy.settings`, `session.settings` (if any), etc.

So:

```python
config.settings is main.settings   # ❌ False after reload
```

## The failure mode

A test that wants to assert behavior driven by an env var does this:

```python
def test_login_success_returns_token_and_interval(monkeypatch):
    monkeypatch.setenv("VPORTAL_FETCH_INTERVAL_MS", "4000")
    from iron_verdict import config
    config.settings.VPORTAL_FETCH_INTERVAL_MS = 4000     # mutate

    response = client.post("/api/vportal/login", json={...})
    assert response.json()["fetch_interval_ms"] == 4000  # ← FAILS: returns 3000
```

When `test_config.py` ran earlier in the same pytest process:

1. `test_config.py` called `reload_config()`. `iron_verdict.config.settings` is now a new object.
2. `vportal_proxy.py` still holds the **old** `settings` reference. Its `VPORTAL_FETCH_INTERVAL_MS` is still `3000` (the default).
3. The test mutates `config.settings.VPORTAL_FETCH_INTERVAL_MS = 4000` — this mutates the **new** object.
4. The login handler reads `settings.VPORTAL_FETCH_INTERVAL_MS` — reads the **old** object → `3000`.
5. Assertion fails. The test passes in isolation (no prior reload) but fails in the full suite.

This is order-dependent and easy to miss locally if you run only the file under development.

## Where it bit us on the VPortal branch

### Task 3 — `test_session_lookup_reports_staging_available_when_env_set`

The plan said to write:
```python
from iron_verdict import config
config.settings.EXPOSE_VPORTAL_STAGING = True
```
…and the implementer agent caught that this would silently no-op (because `main.py` reads from its own `settings` reference). Fix: mutate `iron_verdict.main.settings.EXPOSE_VPORTAL_STAGING` directly.

### Task 6 — `test_login_success_returns_token_and_interval`

Same shape, different module. The implementer used the plan's pattern unchanged. The test passed when the full suite was run for Task 6 because `test_config.py` hadn't yet been reloaded in the right way. Later test additions perturbed the collection order and the failure surfaced. Fix: mutate `iron_verdict.vportal_proxy.settings.VPORTAL_FETCH_INTERVAL_MS` directly via try/finally.

Both fixes are workarounds — the actual defect is upstream.

## Why we end up with `importlib.reload()` at all

`Settings` evaluates `os.getenv(...)` at **class-definition time**, not at attribute-access time:

```python
class Settings:
    VPORTAL_FETCH_INTERVAL_MS: int = _read_fetch_interval()   # ← runs once, at import
```

So testing "what happens when `VPORTAL_FETCH_INTERVAL_MS` env var is set to X" naturally pushes a tester toward `monkeypatch.setenv()` followed by re-evaluating the class body — and `importlib.reload()` is the obvious tool.

## Recommended fixes (pick one)

### Option A — drop `importlib.reload()` from `test_config.py`

Test the parsing helpers directly, not the `Settings` class top-level evaluation:

```python
# in iron_verdict/config.py — already exists, just exposed
def _read_fetch_interval() -> int: ...

# in tests/test_config.py
def test_vportal_fetch_interval_clamps_to_2000_minimum(monkeypatch):
    monkeypatch.setenv("VPORTAL_FETCH_INTERVAL_MS", "500")
    from iron_verdict.config import _read_fetch_interval
    assert _read_fetch_interval() == 2000
```

**Pros:** simplest change. Removes `importlib.reload` entirely. No production code touched.
**Cons:** tests the helper, not the `Settings.VPORTAL_FETCH_INTERVAL_MS` attribute. Slightly less integrated coverage — though the attribute is just `_read_fetch_interval()`, so the gap is small. The `TEST_MODE` and `EXPOSE_VPORTAL_STAGING` tests already use `os.getenv(...) == "1"` inline, so they'd need their own helpers extracted (`_read_test_mode()`, etc.) for symmetry, or stay as integration-via-reload (mixed approach).

### Option B — make `Settings` read env lazily

```python
class Settings:
    @property
    def VPORTAL_FETCH_INTERVAL_MS(self) -> int:
        return _read_fetch_interval()

    @property
    def TEST_MODE(self) -> bool:
        return os.getenv("TEST_MODE") == "1"
    ...
```

**Pros:** `monkeypatch.setenv(...)` alone now Just Works for every test, no reload required. The "same object across all importers" invariant holds permanently.
**Cons:** more invasive — every attribute becomes a property. Reads are slightly more expensive (re-parses env on each access). The `_read_fetch_interval()` helper would log a clamp warning on every access unless rewritten to log once. Decisions about `int(os.getenv(...))` parsing semantics now happen at read time, not at startup; an invalid value could surface mid-request rather than at boot.

### Option C — leave it, document the rule

Keep `importlib.reload()` in `test_config.py` but add a `tests/README.md` or comment in `test_config.py` stating: **"Tests that mutate `settings.X` must mutate `<consumer_module>.settings.X`, not `config.settings.X`, because the test fixture reloads `config` and decouples the names."**

**Pros:** no code changes.
**Cons:** every new test that touches settings has to remember the rule. Easy to forget. Future-you (or another agent) will hit it again.

## Recommendation

**Option A.** The cost is low — split `Settings`'s class-body env reads into named module-level functions (`_read_fetch_interval` already exists; add `_read_test_mode`, `_read_expose_vportal_staging`), and rewrite `test_config.py` to test those helpers directly. The reload-based tests go away entirely, the production code keeps its current shape, and the foot-gun disappears.

If you go this route on a follow-up branch, also revert the two workarounds:

- `tests/test_http.py::test_session_lookup_reports_staging_available_when_env_set` — restore the plan's original `from iron_verdict import config; config.settings.EXPOSE_VPORTAL_STAGING = True` pattern. It'll work once the reload is gone.
- `tests/test_vportal_proxy.py::test_login_success_returns_token_and_interval` — restore similarly. Same reasoning.

(Both currently have inline `Why:` comments pointing back to this issue, so the reverts are mechanical.)
