from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, field_validator
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from judgeme.config import settings
from judgeme.session import SessionManager
from judgeme.connection import ConnectionManager
import json
import copy
import time
import os

class CreateSessionRequest(BaseModel):
    name: str

    @field_validator('name')
    @classmethod
    def name_not_empty(cls, v):
        if not v.strip():
            raise ValueError('name cannot be empty')
        return v.strip()


app = FastAPI(title="JudgeMe")
session_manager = SessionManager()
connection_manager = ConnectionManager()

# Serve static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main HTML page."""
    with open(os.path.join(static_dir, "index.html"), encoding="utf-8") as f:
        return f.read()


@app.post("/api/sessions")
async def create_session(request: CreateSessionRequest):
    """Create a new judging session."""
    code = session_manager.create_session(request.name)
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
                    await websocket.send_json({
                        "type": "join_error",
                        "message": result["error"]
                    })
                    await websocket.close()
                    return

                # Add connection
                await connection_manager.add_connection(session_code, role, websocket)

                # Issue 3: Use deep copy for nested dicts
                session_state = copy.deepcopy(session_manager.sessions[session_code])
                session_state["last_activity"] = session_state["last_activity"].isoformat()

                await websocket.send_json({
                    "type": "join_success",
                    "role": role,
                    "is_head": result["is_head"],
                    "session_state": session_state
                })
            elif message_type == "vote_lock":
                if not session_code or not role:
                    continue

                position = role.replace("_judge", "")
                color = message.get("color")

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

                await connection_manager.broadcast_to_session(
                    session_code,
                    {
                        "type": "timer_start",
                        "server_timestamp": time.time()
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

                session_manager.reset_for_next_lift(session_code)
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
            # Update session state if judge disconnected
            if role.endswith("_judge"):
                position = role.replace("_judge", "")
                if session_code in session_manager.sessions:
                    session_manager.sessions[session_code]["judges"][position]["connected"] = False
