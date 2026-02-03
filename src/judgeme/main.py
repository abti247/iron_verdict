from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from judgeme.session import SessionManager

app = FastAPI(title="JudgeMe")
session_manager = SessionManager()


@app.get("/")
async def root():
    return {"message": "JudgeMe API"}


@app.post("/api/sessions")
async def create_session():
    """Create a new judging session."""
    code = session_manager.create_session()
    return {"session_code": code}
