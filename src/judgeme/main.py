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
                await connection_manager.add_connection(session_code, role, websocket)

                # Send success (serialize datetime objects)
                session_state = session_manager.sessions[session_code].copy()
                session_state["last_activity"] = session_state["last_activity"].isoformat()

                await websocket.send_json({
                    "type": "join_success",
                    "role": role,
                    "is_head": result["is_head"],
                    "session_state": session_state
                })

    except WebSocketDisconnect:
        if session_code and role:
            await connection_manager.remove_connection(session_code, role)
            # Update session state if judge disconnected
            if role.endswith("_judge"):
                position = role.replace("_judge", "")
                if session_code in session_manager.sessions:
                    session_manager.sessions[session_code]["judges"][position]["connected"] = False
