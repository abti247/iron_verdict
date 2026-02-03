from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from judgeme.session import SessionManager
from judgeme.connection import ConnectionManager
import json
import copy

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
                        await connection_manager.broadcast_to_session(
                            session_code,
                            {"type": "show_results", "votes": votes}
                        )
            elif message_type == "timer_start":
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

            elif message_type == "timer_reset":
                if not session_code:
                    continue

                await connection_manager.broadcast_to_session(
                    session_code,
                    {"type": "timer_reset"}
                )
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
