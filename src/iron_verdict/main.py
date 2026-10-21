from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Path
from pydantic import BaseModel, field_validator
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from iron_verdict.config import require_allowed_origin, settings
from iron_verdict.session import SessionManager
from iron_verdict.connection import ConnectionManager
from iron_verdict.vportal_proxy import router as vportal_router
import asyncio
import signal
from contextlib import asynccontextmanager
import json
import copy
import time
import os
import secrets
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware
import logging
from iron_verdict.logging_config import setup_logging

logger = logging.getLogger("iron_verdict")

VALID_COLORS = {"white", "red", "blue", "yellow"}
# Short enough that a half-open connection (typical on venue Wi-Fi when a device
# switches access points) is closed within 15–20 s; the client-side watchdog in
# websocket.js uses the same 15 s limit (3 missed pings). One ping per client
# every 5 s is far below the 20 messages/s rate limit.
HEARTBEAT_INTERVAL_SECONDS = 5
PONG_STALE_SECONDS = 15


async def release_connection(manager: ConnectionManager, session_code: str, role: str, websocket) -> bool:
    """Unregister *websocket* from *role* if it still holds it; return whether it did.

    Used by the WebSocket handler on every exit and by the heartbeat for dead
    connections. A judge released here is marked disconnected on all devices.
    """
    if not await manager.remove_connection_if_current(session_code, role, websocket):
        return False
    if role.endswith("_judge") and session_code in session_manager.sessions:
        position = role.replace("_judge", "")
        session_manager.sessions[session_code]["judges"][position]["connected"] = False
        await manager.broadcast_to_session(
            session_code,
            {"type": "judge_status_update", "position": position, "connected": False},
        )
    return True


async def heartbeat_sweep(manager: ConnectionManager, now: float) -> None:
    """Close connections without a pong for PONG_STALE_SECONDS; ping all others.

    A connection that is closed here or cannot be pinged is removed right away:
    its handler may already have ended and would never clean it up.
    """
    for session_code, role, ws in await manager.get_all_connections():
        log_role = "display" if role.startswith("display_") else role
        last_pong = await manager.get_last_pong(ws)
        if last_pong is not None and now - last_pong > PONG_STALE_SECONDS:
            logger.info("heartbeat_stale_close", extra={
                "session_code": session_code,
                "role": log_role,
                "seconds_since_pong": round(now - last_pong, 1),
            })
            try:
                await ws.close(code=1001)
            except Exception as exc:
                logger.warning("heartbeat_close_failed", extra={"reason": str(exc)})
            await release_connection(manager, session_code, role, ws)
            continue
        try:
            await ws.send_json({"type": "ping"})
        except Exception as exc:
            if await release_connection(manager, session_code, role, ws):
                logger.warning("heartbeat_dead_connection_removed", extra={
                    "session_code": session_code,
                    "role": log_role,
                    "reason": str(exc),
                })


async def cleanup_loop(manager: SessionManager, snapshot_path: str, timeout_hours: int, sleep=asyncio.sleep) -> None:
    """Every minute save the snapshot if it changed (off the event loop); every 30 minutes expire sessions.

    Failures are logged and the loop keeps running: a failed write leaves the last
    written snapshot unchanged, so the next tick retries it.
    """
    elapsed = 0
    while True:
        await sleep(60)
        elapsed += 60
        try:
            await manager.save_snapshot_if_changed(snapshot_path)
        except Exception as exc:
            logger.exception("snapshot_save_failed", extra={"error": str(exc)})
        if elapsed >= 30 * 60:
            elapsed = 0
            try:
                manager.cleanup_expired(timeout_hours)
            except Exception as exc:
                logger.exception("session_cleanup_failed", extra={"error": str(exc)})


def public_pause(pause) -> dict | None:
    """The pause as clients see it: end in epoch ms, without the internal id."""
    if pause is None:
        return None
    return {
        "end_at_ms": int(pause["end_at"] * 1000),
        "mode": pause["mode"],
        "next_lift": pause["next_lift"],
    }


def pause_update_message(pause) -> dict:
    # server_now_ms lets each display count down against the server clock (#163).
    return {"type": "pause_update", "pause": public_pause(pause), "server_now_ms": int(time.time() * 1000)}


# One automatic pause end per session (#163). The server decides the end, so a
# display with a wrong clock or without a connection cannot end it early or late.
_pause_end_tasks: dict[str, asyncio.Task] = {}


async def end_pause_when_due(session_code: str, pause_id: str, end_at: float, sleep=asyncio.sleep) -> None:
    """Wait until *end_at*, then end that pause (if it still runs) on every device.

    The wait is the pause itself (its end time chosen on a display), not an
    artificial delay.
    """
    await sleep(max(0.0, end_at - time.time()))
    if session_manager.end_pause(session_code, pause_id=pause_id):
        logger.info("pause_ended", extra={"session_code": session_code, "ended_by": "time"})
        await connection_manager.broadcast_to_session(session_code, pause_update_message(None))


def schedule_pause_end(session_code: str) -> None:
    """(Re)arm the automatic end for the session's current pause; cancel it if none runs."""
    old = _pause_end_tasks.pop(session_code, None)
    if old is not None:
        old.cancel()
    pause = session_manager.sessions.get(session_code, {}).get("pause")
    if pause is None:
        return
    task = asyncio.create_task(end_pause_when_due(session_code, pause["id"], pause["end_at"]))
    _pause_end_tasks[session_code] = task

    def forget(done: asyncio.Task) -> None:
        if _pause_end_tasks.get(session_code) is done:
            del _pause_end_tasks[session_code]

    task.add_done_callback(forget)


def restore_pause_timers() -> None:
    """After loading the snapshot: arm the end of every restored pause (an expired one ends at once)."""
    for session_code, session in list(session_manager.sessions.items()):
        if session.get("pause") is not None:
            schedule_pause_end(session_code)


def _client_ip(headers, client) -> str:
    # Production runs behind Cloudflare and Railway's edge proxy: the TCP peer
    # is a Railway 100.64.0.0/10 address that changes even for one client.
    # Cloudflare sets CF-Connecting-IP to the real client and overwrites any
    # value the client sends. X-Forwarded-For is not used: its first entry is
    # whatever the client put there.
    cf_ip = headers.get("cf-connecting-ip", "").strip()
    if cf_ip:
        return cf_ip
    return client.host if client else "unknown"


def _get_http_client_ip(request: Request) -> str:
    return _client_ip(request.headers, request.client)


def _get_ws_client_ip(websocket: WebSocket) -> str:
    return _client_ip(websocket.headers, websocket.client)


class CreateSessionRequest(BaseModel):
    name: str
    kind: str = "generic"

    @field_validator('name')
    @classmethod
    def name_not_empty(cls, v):
        if not v.strip():
            raise ValueError('name cannot be empty')
        return v.strip()

    @field_validator('kind')
    @classmethod
    def kind_valid(cls, v):
        if v not in {"generic", "vportal"}:
            raise ValueError("kind must be 'generic' or 'vportal'")
        return v


_CSP = (
    "default-src 'self'; "
    "script-src 'self' https://umami-production-ca4a.up.railway.app 'unsafe-inline' 'unsafe-eval'; "
    "connect-src 'self' ws: wss: https://api.web3forms.com https://umami-production-ca4a.up.railway.app; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "font-src 'self'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = _CSP
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


limiter = Limiter(key_func=_get_http_client_ip)
session_manager = SessionManager()
connection_manager = ConnectionManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.LOG_LEVEL)
    require_allowed_origin(settings.ALLOWED_ORIGIN)
    logger.info("rate_limits_configured", extra={
        "session_create": settings.RATE_LIMIT_SESSION_CREATE,
        "session_lookup": settings.RATE_LIMIT_SESSION_LOOKUP,
    })
    session_manager.load_snapshot(settings.SNAPSHOT_PATH)
    restore_pause_timers()

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

        _shutdown_triggered = False

        def _signal_handler():
            nonlocal _shutdown_triggered
            if _shutdown_triggered:
                return
            _shutdown_triggered = True
            asyncio.create_task(_handle_shutdown())

        try:
            loop.add_signal_handler(signal.SIGTERM, _signal_handler)
            loop.add_signal_handler(signal.SIGINT, _signal_handler)
        except (NotImplementedError, OSError):
            pass  # Windows or non-main thread

    task = asyncio.create_task(
        cleanup_loop(session_manager, settings.SNAPSHOT_PATH, settings.SESSION_TIMEOUT_HOURS)
    )

    async def _heartbeat_loop():
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
            await heartbeat_sweep(connection_manager, time.monotonic())

    heartbeat_task = asyncio.create_task(_heartbeat_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    heartbeat_task.cancel()
    try:
        await heartbeat_task
    except asyncio.CancelledError:
        pass
    # The pause itself is in the snapshot; its end is armed again after the restart.
    for pause_task in list(_pause_end_tasks.values()):
        pause_task.cancel()

    # Fallback snapshot save for shutdowns not triggered via signal handler
    session_manager.save_snapshot(settings.SNAPSHOT_PATH)

app = FastAPI(title="Iron Verdict", lifespan=lifespan)
app.include_router(vportal_router)
app.add_middleware(SecurityHeadersMiddleware)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("unhandled_exception", extra={"client_ip": _get_http_client_ip(request)})
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

class RevalidatedStaticFiles(StaticFiles):
    """StaticFiles whose responses the browser must revalidate before each use.

    Without Cache-Control, browsers reuse files heuristically without asking,
    so after a deploy new HTML could run with old cached JavaScript. With
    no-cache they keep the file but send If-None-Match; unchanged files come
    back as 304 without a body.
    """

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


# Serve static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", RevalidatedStaticFiles(directory=static_dir), name="static")


@app.get("/health")
async def health():
    return {"status": "ok"}


def _serve_index() -> Response:
    with open(os.path.join(static_dir, "index.html"), encoding="utf-8") as f:
        content = f.read().replace("__APP_VERSION__", settings.APP_VERSION)
    return Response(
        content=content,
        media_type="text/html",
        headers={"Cache-Control": "no-cache"},
    )


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main HTML page (generic sessions)."""
    return _serve_index()


@app.get("/vportal", response_class=HTMLResponse)
async def vportal_root():
    """Same HTML as `/`; the client reads location.pathname to decide kind on create."""
    return _serve_index()


@app.post("/api/sessions")
@limiter.limit(settings.RATE_LIMIT_SESSION_CREATE)
async def create_session(request: Request, body: CreateSessionRequest):
    """Create a new judging session."""
    code = await session_manager.create_session(body.name, kind=body.kind)
    logger.info(
        "session_created",
        extra={"session_code": code, "kind": body.kind, "client_ip": _get_http_client_ip(request)},
    )
    return {"session_code": code}


@app.get("/api/sessions/{code}")
@limiter.limit(settings.RATE_LIMIT_SESSION_LOOKUP)
async def get_session(
    request: Request,
    code: str = Path(..., pattern=r"^[A-Z0-9]{8}$"),
):
    """Look up an active session. Used by:
       - landing-screen code validation (checks `exists`)
       - role-select to decide whether to show the VPortal connect button (reads `kind`)
       - the connect modal to decide whether to surface the staging option (reads `staging_available`)
    """
    if code in session_manager.sessions:
        session = session_manager.sessions[code]
        return {
            "exists": True,
            "kind": session["kind"],
            "staging_available": settings.EXPOSE_VPORTAL_STAGING,
        }
    logger.info("session_lookup_not_found", extra={
        "session_code": code,
        "client_ip": _get_http_client_ip(request),
    })
    return JSONResponse(status_code=404, content={"detail": "Session not found"})


def _holds_valid_reconnect_token(session_code: str, role: str, token) -> bool:
    """Whether *token* is the current reconnect token of the judge *role*."""
    if not token or not role.endswith("_judge"):
        return False
    position = role.replace("_judge", "")
    judge = session_manager.sessions.get(session_code, {}).get("judges", {}).get(position, {})
    return judge.get("reconnect_token") == token


async def _reject_vote(websocket: WebSocket, conn_id: str, session_code: str, role: str, code: str, text: str) -> None:
    logger.info("vote_rejected", extra={
        "conn_id": conn_id,
        "session_code": session_code,
        "role": "display" if role.startswith("display_") else role,
        "code": code,
        "reason": text,
    })
    await websocket.send_json({"type": "vote_rejected", "code": code, "message": text})


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time communication."""
    conn_id = secrets.token_hex(8)
    origin = websocket.headers.get("origin", "")
    if settings.ALLOWED_ORIGIN != "*" and origin != settings.ALLOWED_ORIGIN:
        logger.warning("origin_rejected", extra={
            "conn_id": conn_id,
            "origin": origin,
            "client_ip": _get_ws_client_ip(websocket),
        })
        await websocket.close(code=1008)
        return
    await websocket.accept()

    session_code = None
    role = None
    # True while this socket is registered in connection_manager under role;
    # the finally block below releases it on every way the handler ends.
    registered = False

    msg_count = 0
    window_start = time.monotonic()

    try:
        while True:
            data = await websocket.receive_text()

            now = time.monotonic()
            if now - window_start >= 1.0:
                window_start = now
                msg_count = 1
            else:
                msg_count += 1
            if msg_count > 20:
                logger.warning("message_flood_disconnect", extra={"conn_id": conn_id, "client_ip": _get_ws_client_ip(websocket)})
                await websocket.close(code=1008)
                return

            # Issue 1: Add error handling for JSON parsing
            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON format"
                })
                continue

            # Issue 2: Use .get() method with validation
            message_type = message.get("type")
            if message_type == "join":
                if registered:
                    # The client sends one join per socket; a second one must not
                    # register this socket under a second role (#136).
                    logger.warning("second_join_rejected", extra={
                        "conn_id": conn_id,
                        "session_code": session_code,
                        "role": "display" if role.startswith("display_") else role,
                    })
                    await websocket.send_json({"type": "error", "message": "Already joined"})
                    continue
                session_code = (message.get("session_code") or "").upper()
                role = message.get("role")

                if not session_code or not role:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Missing required fields"
                    })
                    continue

                # Global cap (#61), checked before join_session so a rejected judge is
                # never marked connected. Not exact: concurrent joins may pass it
                # together. A judge with a valid reconnect token is exempt — it only
                # replaces its own connection, which may still be counted.
                if (
                    not _holds_valid_reconnect_token(session_code, role, message.get("reconnect_token"))
                    and await connection_manager.count_connections() >= settings.MAX_WEBSOCKETS
                ):
                    logger.warning("websocket_cap_reached", extra={
                        "conn_id": conn_id,
                        "session_code": session_code,
                        "role": role,
                        "limit": settings.MAX_WEBSOCKETS,
                        "client_ip": _get_ws_client_ip(websocket),
                    })
                    await websocket.send_json({
                        "type": "join_error",
                        "message": "Server at capacity"
                    })
                    await websocket.close(code=1013)
                    return

                # Validate join
                result = session_manager.join_session(session_code, role)

                if not result["success"]:
                    if result["error"] == "Role already taken" and role.endswith("_judge"):
                        position = role.replace("_judge", "")
                        stored_token = message.get("reconnect_token")
                        judge = session_manager.sessions.get(session_code, {}).get("judges", {}).get(position, {})
                        judge_token = judge.get("reconnect_token")
                        if stored_token and judge_token and stored_token == judge_token:
                            # Valid reconnect token — close old connection and take the slot
                            old_ws = await connection_manager.get_connection(session_code, role)
                            if old_ws:
                                await connection_manager.remove_connection(session_code, role)
                                try:
                                    await old_ws.close()
                                except Exception:
                                    pass
                            # Re-check the token: during the awaits above a concurrent reconnect
                            # with the same token may have taken the slot and rotated the token.
                            # From here to join_session there must be no await (#57).
                            judge = session_manager.sessions.get(session_code, {}).get("judges", {}).get(position, {})
                            if judge.get("reconnect_token") == stored_token:
                                judge["connected"] = False
                                result = session_manager.join_session(session_code, role)
                    if not result["success"]:
                        logger.warning("role_join_failed", extra={
                            "conn_id": conn_id,
                            "session_code": session_code,
                            "role": message.get("role"),
                            "reason": result["error"],
                            "client_ip": _get_ws_client_ip(websocket),
                        })
                        await websocket.send_json({
                            "type": "join_error",
                            "message": result["error"]
                        })
                        await websocket.close()
                        return

                if role == "display":
                    if await connection_manager.count_displays(session_code) >= settings.DISPLAY_CAP:
                        await websocket.send_json({
                            "type": "join_error",
                            "message": "Display cap reached"
                        })
                        await websocket.close()
                        return
                    role = f"display_{secrets.token_hex(4)}"

                # Add connection
                await connection_manager.add_connection(session_code, role, websocket)
                registered = True
                logger.info("role_joined", extra={
                    "conn_id": conn_id,
                    "session_code": session_code,
                    "role": "display" if role.startswith("display_") else role,
                    "client_ip": _get_ws_client_ip(websocket),
                })

                # Issue 3: Use deep copy for nested dicts
                session_state = copy.deepcopy(session_manager.sessions[session_code])
                session_state["pause"] = public_pause(session_state.get("pause"))
                session_state["server_now_ms"] = int(time.time() * 1000)
                session_state["last_activity"] = session_state["last_activity"].isoformat()
                # Do not expose other judges' reconnect tokens to clients
                for judge in session_state["judges"].values():
                    judge.pop("reconnect_token", None)

                # Compute time_remaining_ms for late-joining clients
                if session_state.get("timer_started_at"):
                    elapsed_ms = (time.time() - session_state["timer_started_at"]) * 1000
                    session_state["time_remaining_ms"] = max(0, 60000 - elapsed_ms)
                else:
                    session_state["time_remaining_ms"] = None

                await websocket.send_json({
                    "type": "join_success",
                    "role": "display" if role.startswith("display_") else role,
                    "is_head": result["is_head"],
                    "session_state": session_state,
                    "reconnect_token": result.get("reconnect_token"),
                })
                # If session is in results phase, replay show_results to the rejoining client
                rejoined_session = session_manager.sessions.get(session_code)
                if rejoined_session and rejoined_session.get("phase") == "results":
                    r_judges = rejoined_session["judges"]
                    r_votes = {
                        pos: j["current_vote"]
                        for pos, j in r_judges.items()
                        if j["locked"]
                    }
                    r_reasons = {
                        pos: j["current_reason"]
                        for pos, j in r_judges.items()
                        if j["locked"]
                    }
                    r_settings = rejoined_session["settings"]
                    await websocket.send_json({
                        "type": "show_results",
                        "votes": r_votes,
                        "reasons": r_reasons,
                        "showExplanations": r_settings["show_explanations"],
                        "liftType": r_settings["lift_type"],
                        "timer_frozen_ms": rejoined_session.get("timer_frozen_ms"),
                    })
                if role.endswith("_judge"):
                    position = role.replace("_judge", "")
                    await connection_manager.broadcast_to_others(
                        session_code,
                        websocket,
                        {"type": "judge_status_update", "position": position, "connected": True},
                    )
            elif message_type == "vote_lock":
                if not session_code or not role:
                    continue

                # Every vote_lock gets exactly one answer to the voter: vote_ack or
                # vote_rejected. The judge UI shows "sending" until one arrives.
                async def reject_vote(code: str, text: str) -> None:
                    await _reject_vote(websocket, conn_id, session_code, role, code, text)

                position = role.replace("_judge", "")
                color = message.get("color")

                if color not in VALID_COLORS:
                    await reject_vote("invalid", "Invalid vote color")
                    continue

                reason = message.get("reason")
                if reason is not None and (not isinstance(reason, str) or len(reason) > 200):
                    await reject_vote("invalid", "Invalid reason")
                    continue

                lift_id = message.get("lift_id")
                if lift_id is not None and (not isinstance(lift_id, int) or isinstance(lift_id, bool)):
                    await reject_vote("invalid", "Invalid lift id")
                    continue

                result = await session_manager.lock_vote(session_code, position, color, reason=reason, lift_id=lift_id)

                if not result["success"]:
                    if result["error"] == "Vote already locked":
                        # Idempotent: a resend after reconnect must not fail. The stored
                        # vote is authoritative, even if the resend carried another colour.
                        await websocket.send_json({
                            "type": "vote_ack",
                            "color": result["current_vote"],
                            "reason": result["current_reason"],
                            "lift_id": session_manager.sessions[session_code]["lift_id"],
                        })
                    elif result["error"] == "Lift changed":
                        await reject_vote("lift_changed", result["error"])
                    elif result["error"] == "Reason required":
                        await reject_vote("reason_required", "Reason required before locking in")
                    else:
                        await reject_vote("invalid", result["error"])
                    continue

                if result["success"]:
                    logger.info("vote_locked", extra={
                        "conn_id": conn_id,
                        "session_code": session_code,
                        "position": position,
                        "color": color,
                        "all_locked": result.get("all_locked", False),
                    })
                    await websocket.send_json({
                        "type": "vote_ack",
                        "color": color,
                        "reason": reason,
                        "lift_id": session_manager.sessions[session_code]["lift_id"],
                    })
                    # Notify display that a judge voted (no color)
                    await connection_manager.send_to_displays(
                        session_code,
                        {"type": "judge_voted", "position": position}
                    )

                    # If all locked, broadcast results
                    if result.get("all_locked"):
                        judges = session_manager.sessions[session_code]["judges"]
                        votes = {
                            pos: judge["current_vote"]
                            for pos, judge in judges.items()
                            if judge["connected"]
                        }
                        reasons = {
                            pos: judge["current_reason"]
                            for pos, judge in judges.items()
                            if judge["connected"]
                        }
                        session_settings = session_manager.sessions[session_code]["settings"]
                        await connection_manager.broadcast_to_session(
                            session_code,
                            {
                                "type": "show_results",
                                "votes": votes,
                                "reasons": reasons,
                                "showExplanations": session_settings["show_explanations"],
                                "liftType": session_settings["lift_type"],
                                "timer_frozen_ms": session_manager.sessions[session_code].get("timer_frozen_ms"),
                            }
                        )
            elif message_type == "timer_start":
                if not session_code or not role:
                    continue

                # Only head judge can control timer
                if role != "center_judge":
                    await websocket.send_json({
                        "type": "error",
                        "message": "Only head judge can control timer"
                    })
                    continue

                logger.info("timer_start", extra={"conn_id": conn_id, "session_code": session_code})
                # Starting the timer ends a pause (#163), on every display before the timer shows.
                if session_manager.end_pause(session_code):
                    schedule_pause_end(session_code)
                    logger.info("pause_ended", extra={"conn_id": conn_id, "session_code": session_code, "ended_by": "timer_start"})
                    await connection_manager.broadcast_to_session(session_code, pause_update_message(None))
                session_manager.sessions[session_code]["timer_started_at"] = time.time()
                await connection_manager.broadcast_to_session(
                    session_code,
                    {
                        "type": "timer_start",
                        "time_remaining_ms": 60000
                    }
                )

            elif message_type == "timer_reset":
                if not session_code or not role:
                    continue

                # Only head judge can control timer
                if role != "center_judge":
                    await websocket.send_json({
                        "type": "error",
                        "message": "Only head judge can control timer"
                    })
                    continue

                logger.info("timer_reset", extra={"conn_id": conn_id, "session_code": session_code})
                session_manager.sessions[session_code]["timer_started_at"] = None
                session_manager.sessions[session_code]["phase"] = "voting"
                session_manager.sessions[session_code]["timer_frozen_ms"] = None
                await connection_manager.broadcast_to_session(
                    session_code,
                    {"type": "timer_reset"}
                )

            elif message_type == "next_lift":
                if not session_code or not role:
                    continue

                # Only head judge can advance to next lift
                if role != "center_judge":
                    await websocket.send_json({
                        "type": "error",
                        "message": "Only head judge can advance to next lift"
                    })
                    continue

                logger.info("next_lift", extra={"conn_id": conn_id, "session_code": session_code})
                reset = await session_manager.reset_for_next_lift(session_code)
                await connection_manager.broadcast_to_session(
                    session_code,
                    {"type": "reset_for_next_lift", "lift_id": reset.get("lift_id")}
                )

            elif message_type == "end_session_confirmed":
                if not session_code or not role:
                    continue

                # Only head judge can end session
                if role != "center_judge":
                    await websocket.send_json({
                        "type": "error",
                        "message": "Only head judge can end session"
                    })
                    continue

                logger.info("session_ended", extra={"conn_id": conn_id, "session_code": session_code})
                await connection_manager.broadcast_to_session(
                    session_code,
                    {"type": "session_ended", "reason": "head_judge"}
                )

                # Close all connections first (with proper cleanup)
                if session_code in connection_manager.active_connections:
                    # Get list of connections to avoid dict mutation during iteration
                    connections = list(connection_manager.active_connections[session_code].items())
                    for conn_role, ws in connections:
                        try:
                            await ws.close()
                        except Exception:
                            logger.warning("ws_close_failed", exc_info=True, extra={"conn_id": conn_id})
                        # Remove from connection manager
                        await connection_manager.remove_connection(session_code, conn_role)

                # Finally, delete session data and exit — the websocket was
                # closed above; returning prevents receive_text() from being
                # called on a dead connection, which would raise RuntimeError.
                session_manager.delete_session(session_code)
                schedule_pause_end(session_code)  # no session, no pause: cancels its end
                registered = False
                return
            elif message_type == "settings_update":
                if not session_code or not role:
                    continue
                if role != "center_judge":
                    await websocket.send_json({
                        "type": "error",
                        "message": "Only head judge can update settings"
                    })
                    continue
                result = session_manager.update_settings(
                    session_code,
                    message.get("showExplanations", True),
                    message.get("liftType", "squat"),
                    require_reasons=message.get("requireReasons", False),
                )
                if not result["success"]:
                    await websocket.send_json({
                        "type": "error",
                        "message": result["error"]
                    })
                else:
                    # Broadcast settings update to all connected clients
                    session_settings = session_manager.sessions[session_code]["settings"]
                    await connection_manager.broadcast_to_session(
                        session_code,
                        {
                            "type": "settings_update",
                            "showExplanations": session_settings["show_explanations"],
                            "liftType": session_settings["lift_type"],
                            "requireReasons": session_settings["require_reasons"],
                        }
                    )
            elif message_type in ("pause_start", "pause_end"):
                if not session_code or not role:
                    continue
                # Started and ended from a display's settings panel only (#163).
                if not role.startswith("display_"):
                    await websocket.send_json({
                        "type": "error",
                        "message": "Only displays can control the pause"
                    })
                    continue
                if message_type == "pause_start":
                    result = session_manager.start_pause(
                        session_code,
                        minutes=message.get("minutes"),
                        end_at_ms=message.get("end_at_ms"),
                        next_lift=message.get("next_lift"),
                    )
                    if not result["success"]:
                        # Every pause_start gets one answer to the sender: pause_update or pause_rejected.
                        await websocket.send_json({"type": "pause_rejected", "code": result["error"]})
                        continue
                    logger.info("pause_started", extra={
                        "conn_id": conn_id,
                        "session_code": session_code,
                        "pause_mode": result["pause"]["mode"],
                        "pause_seconds": round(result["pause"]["end_at"] - time.time()),
                    })
                else:
                    if session_manager.end_pause(session_code):
                        logger.info("pause_ended", extra={"conn_id": conn_id, "session_code": session_code, "ended_by": "display"})
                schedule_pause_end(session_code)
                # Also sent when no pause ran, so the sender's display shows the real state.
                await connection_manager.broadcast_to_session(
                    session_code,
                    pause_update_message(session_manager.sessions[session_code]["pause"]),
                )
            elif message_type == "pong":
                await connection_manager.mark_pong(websocket)
                continue
            else:
                # Issue 4: Handle post-join messages
                # For now, just ignore unknown message types silently
                pass

    except WebSocketDisconnect:
        pass
    finally:
        if registered:
            log_extra = {
                "conn_id": conn_id,
                "session_code": session_code,
                "role": "display" if role.startswith("display_") else role,
            }
            if await release_connection(connection_manager, session_code, role, websocket):
                logger.info("role_disconnected", extra=log_extra)
            else:
                # Replaced by a reconnect or already removed by the heartbeat
                logger.info("stale_disconnect_ignored", extra=log_extra)
