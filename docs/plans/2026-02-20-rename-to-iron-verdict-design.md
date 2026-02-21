# Rename: judgeme → Iron Verdict

**Date:** 2026-02-20

## Goal

Replace all `judgeme` / `JudgeMe` identifiers with `iron_verdict` / `Iron Verdict` across the codebase. The root project folder and historical plan docs are left untouched.

## Approach

Layered edits in a worktree, with tests run after each layer.

## Change Inventory

| File | Old | New |
|---|---|---|
| `src/judgeme/` (directory) | `judgeme/` | `iron_verdict/` |
| `pyproject.toml` | `name = "judgeme"` | `name = "iron-verdict"` |
| `run.py` | `"judgeme.main:app"` | `"iron_verdict.main:app"` |
| `src/*/main.py`, `connection.py`, `logging_config.py` | `from judgeme.xxx` | `from iron_verdict.xxx` |
| `src/*/main.py`, `connection.py`, `logging_config.py` | `getLogger("judgeme")` | `getLogger("iron_verdict")` |
| `src/*/main.py` | `FastAPI(title="JudgeMe")` | `FastAPI(title="Iron Verdict")` |
| `src/*/static/index.html` | `judgemeApp()` (×2) | `ironVerdictApp()` (×2) |
| `tests/*.py` (4 files) | `from judgeme.xxx` | `from iron_verdict.xxx` |
| `README.md` | `# JudgeMe` | `# Iron Verdict` |

## Layers

1. **Package structure** — Rename `src/judgeme/` → `src/iron_verdict/`, update `pyproject.toml`. Reinstall package. Run tests.
2. **Code references** — Update imports, logger names, ASGI path, FastAPI title, Alpine function name. Run tests.
3. **Docs** — Update `README.md`.

## Out of Scope

- Root folder rename (`judgeme/`)
- Historical plan docs (`docs/plans/`)
