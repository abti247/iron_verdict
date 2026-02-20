from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from pydantic import BaseModel, field_validator
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from judgeme.config import settings
from judgeme.session import SessionManager
from judgeme.connection import ConnectionManager
import asyncio
from contextlib import asynccontextmanager
import json
import copy
import time
import os
import secrets
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware
import logging
from judgeme.logging_config import setup_logging

logger = logging.getLogger("judgeme")

VALID_COLORS = {"white", "red", "blue", "yellow"}


def _get_http_client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "unknown")


def _get_ws_client_ip(websocket: WebSocket) -> str:
    fwd = websocket.headers.get("x-forwarded-for")
    return fwd.split(",")[0].strip() if fwd else (websocket.client.host if websocket.client else "unknown")


class CreateSessionRequest(BaseModel):
    name: str

    @field_validator('name')
    @classmethod
    def name_not_empty(cls, v):
        if not v.strip():
            raise ValueError('name cannot be empty')
        return v.strip()


_CSP = (
    "default-src 'self'; "
    "script-src 'self' https://cdn.jsdelivr.net 'unsafe-inline' 'unsafe-eval'; "
    "connect-src 'self' ws: wss:; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "img-src 'self' data:; "
    "font-src 'self' https://fonts.gstatic.com"
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


limiter = Limiter(key_func=get_remote_address)
session_manager = SessionManager()
connection_manager = ConnectionManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()

    async def _cleanup_loop():
        while True:
            await asyncio.sleep(30 * 60)
            session_manager.cleanup_expired(settings.SESSION_TIMEOUT_HOURS)

    task = asyncio.create_task(_cleanup_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

app = FastAPI(title="JudgeMe", lifespan=lifespan)
app.add_middleware(SecurityHeadersMiddleware)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Serve static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main HTML page."""
    with open(os.path.join(static_dir, "index.html"), encoding="utf-8") as f:
        content = f.read()
    return Response(
        content=content,
        media_type="text/html",
        headers={"Cache-Control": "no-cache"},
    )


@app.post("/api/sessions")
@limiter.limit("10/hour")
async def create_session(request: Request, body: CreateSessionRequest):
    """Create a new judging session."""
    code = await session_manager.create_session(body.name)
    logger.info("session_created", extra={"session_code": code, "client_ip": _get_http_client_ip(request)})
    return {"session_code": code}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time communication."""
    origin = websocket.headers.get("origin", "")
    if settings.ALLOWED_ORIGIN != "*" and origin != settings.ALLOWED_ORIGIN:
        logger.warning("origin_rejected", extra={
            "origin": origin,
            "client_ip": _get_ws_client_ip(websocket),
        })
        await websocket.close(code=1008)
        return
    await websocket.accept()

    session_code = None
    role = None

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
                logger.warning("message_flood_disconnect", extra={"client_ip": _get_ws_client_ip(websocket)})
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
                session_code = message.get("session_code")
                role = message.get("role")

                if not session_code or not role:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Missing required fields"
                    })
                    continue

                # Validate join
                result = session_manager.join_session(session_code, role)

                if not result["success"]:
                    logger.warning("role_join_failed", extra={
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
                logger.info("role_joined", extra={
                    "session_code": session_code,
                    "role": "display" if role.startswith("display_") else role,
                    "client_ip": _get_ws_client_ip(websocket),
                })

                # Issue 3: Use deep copy for nested dicts
                session_state = copy.deepcopy(session_manager.sessions[session_code])
                session_state["last_activity"] = session_state["last_activity"].isoformat()

                await websocket.send_json({
                    "type": "join_success",
                    "role": "display" if role.startswith("display_") else role,
                    "is_head": result["is_head"],
                    "session_state": session_state
                })
            elif message_type == "vote_lock":
                if not session_code or not role:
                    continue

                position = role.replace("_judge", "")
                color = message.get("color")

                if color not in VALID_COLORS:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Invalid vote color"
                    })
                    continue

                result = await session_manager.lock_vote(session_code, position, color)

                if result["success"]:
                    logger.info("vote_locked", extra={
                        "session_code": session_code,
                        "position": position,
                        "color": color,
                        "all_locked": result.get("all_locked", False),
                    })
                    # Notify display that a judge voted (no color)
                    await connection_manager.send_to_displays(
                        session_code,
                        {"type": "judge_voted", "position": position}
                    )

                    # If all locked, broadcast results
                    if result.get("all_locked"):
                        votes = {
                            pos: judge["current_vote"]
                            for pos, judge in session_manager.sessions[session_code]["judges"].items()
                            if judge["connected"]
                        }
                        session_settings = session_manager.sessions[session_code]["settings"]
                        await connection_manager.broadcast_to_session(
                            session_code,
                            {
                                "type": "show_results",
                                "votes": votes,
                                "showExplanations": session_settings["show_explanations"],
                                "liftType": session_settings["lift_type"],
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

                logger.info("timer_start", extra={"session_code": session_code})
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

                logger.info("timer_reset", extra={"session_code": session_code})
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

                logger.info("next_lift", extra={"session_code": session_code})
                await session_manager.reset_for_next_lift(session_code)
                await connection_manager.broadcast_to_session(
                    session_code,
                    {"type": "reset_for_next_lift"}
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

                logger.info("session_ended", extra={"session_code": session_code})
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
                            pass  # Connection already closed
                        # Remove from connection manager
                        await connection_manager.remove_connection(session_code, conn_role)

                # Finally, delete session data
                session_manager.delete_session(session_code)
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
                    message.get("showExplanations", False),
                    message.get("liftType", "squat")
                )
                if not result["success"]:
                    await websocket.send_json({
                        "type": "error",
                        "message": result["error"]
                    })
            else:
                # Issue 4: Handle post-join messages
                # For now, just ignore unknown message types silently
                pass

    except WebSocketDisconnect:
        if session_code and role:
            await connection_manager.remove_connection(session_code, role)
            logger.info("role_disconnected", extra={
                "session_code": session_code,
                "role": "display" if role.startswith("display_") else role,
            })
            # Update session state if judge disconnected
            if role.endswith("_judge"):
                position = role.replace("_judge", "")
                if session_code in session_manager.sessions:
                    session_manager.sessions[session_code]["judges"][position]["connected"] = False
