# Server Restart UX Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Show "Server restarting" text near the connection status dot when the server broadcasts a restart, so users can distinguish a server shutdown from a connection drop.

**Architecture:** Two independent fixes. (1) Backend: swap snapshot save before client broadcast in lifespan shutdown so the snapshot is never lost if SIGKILL arrives during the broadcast. (2) Frontend: track a `serverRestarting` flag; set it when the `server_restarting` WS message arrives; show a small label near the conn-dot on judge and display screens while the flag is set; clear it on reconnect.

**Tech Stack:** Python/FastAPI lifespan, Alpine.js, vanilla JS (app.js, handlers.js), index.html

> **Note:** Tasks 1-3 are complete. Task 4 added after discovering that uvicorn closes WebSocket connections *before* the lifespan teardown runs, so the broadcast in lifespan teardown always fires to nobody. Fix: intercept SIGTERM/SIGINT with our own signal handler that broadcasts first, then triggers uvicorn shutdown via `server.should_exit = True`.

---

### Task 1: Fix snapshot save order in lifespan shutdown (done)

### Task 2: Add serverRestarting state and handler (done)

### Task 3: Show "Server restarting" label in the UI (done)

---

### Task 4: Signal handler to broadcast before uvicorn closes connections

**Root cause:** Uvicorn closes WebSocket connections during graceful shutdown *before* the lifespan teardown code runs. The broadcast in the lifespan teardown finds no active connections.

**Fix:** Register SIGTERM and SIGINT handlers in lifespan startup (only when `app.state.uvicorn_server` is set). These handlers broadcast `server_restarting` first, then set `server.should_exit = True` to trigger uvicorn's normal graceful shutdown. Remove the now-dead broadcast block from lifespan teardown; keep `save_snapshot` there as a fallback.

**Files:**
- Modify: `run.py`
- Modify: `src/iron_verdict/main.py`

**Step 1: Update run.py**

Replace the entire `if __name__ == "__main__":` block:

```python
if __name__ == "__main__":
    reload = os.getenv("ENV") == "development"
    if reload:
        uvicorn.run(
            "iron_verdict.main:app",
            host=settings.HOST,
            port=settings.PORT,
            reload=True,
        )
    else:
        import asyncio
        from iron_verdict.main import app
        config = uvicorn.Config(
            "iron_verdict.main:app",
            host=settings.HOST,
            port=settings.PORT,
        )
        server = uvicorn.Server(config)
        app.state.uvicorn_server = server
        asyncio.run(server.serve())
```

**Step 2: Add signal handlers in lifespan startup**

Add `import signal` to the imports at the top of `src/iron_verdict/main.py`.

In the lifespan function, after `session_manager.load_snapshot(...)` and before `_cleanup_loop`, add:

```python
loop = asyncio.get_running_loop()
uvicorn_server = getattr(app.state, "uvicorn_server", None)

if uvicorn_server:
    async def _handle_shutdown():
        logger.info("server_shutdown_started")
        session_manager.save_snapshot(settings.SNAPSHOT_PATH)
        for session_code in list(connection_manager.active_connections.keys()):
            await connection_manager.broadcast_to_session(
                session_code,
                {"type": "server_restarting"}
            )
        uvicorn_server.should_exit = True

    def _signal_handler():
        asyncio.create_task(_handle_shutdown())

    try:
        loop.add_signal_handler(signal.SIGTERM, _signal_handler)
        loop.add_signal_handler(signal.SIGINT, _signal_handler)
    except (NotImplementedError, OSError):
        pass  # Windows or non-main thread
```

**Step 3: Clean up lifespan teardown**

Remove the broadcast block after `yield` (dead code — connections already closed by teardown time).
Replace these lines:

```python
    # Graceful shutdown: save state first, then notify all clients
    logger.info("server_shutdown_started")
    session_manager.save_snapshot(settings.SNAPSHOT_PATH)
    for session_code in list(connection_manager.active_connections.keys()):
        await connection_manager.broadcast_to_session(
            session_code,
            {"type": "server_restarting"}
        )
```

With:

```python
    # Fallback snapshot save for shutdowns not triggered via signal handler
    session_manager.save_snapshot(settings.SNAPSHOT_PATH)
```

**Step 4: Run tests**

```bash
python -m pytest --tb=short -q
```

Expected: 88 passed.

**Step 5: Commit**

```bash
git add run.py src/iron_verdict/main.py
git commit -m "fix: broadcast server_restarting via signal handler before uvicorn closes connections"
```

**Step 6: Manual verification**

Start app with `python run.py`, join session as judge, Ctrl+C.
Expected: orange dot + "Server restarting" label appears.

Docker: `docker compose up --build`, join session, `docker stop <container>`.
Expected: same.
