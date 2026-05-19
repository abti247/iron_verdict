"""Tiny FastAPI app that mimics the subset of VPortal Iron Verdict consumes."""

from urllib.parse import parse_qs

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

app = FastAPI()

STATE = {
    "credentials": {"u": "p"},  # default fake creds
    "active_attempt": {
        "id": "A-1", "attempt": 2, "discipline": "SQUAT", "weight": 215, "status": None,
        "competitionAthlete": {
            "firstName": "Maria", "lastName": "Schneider",
            "club": {"name": "SV Eisenkraft Berlin"},
            "bodyWeightCategory": {"name": "-72 kg"},
            "ageCategory": {"name": "Open"},
        },
    },
    "stages": [{"id": "STAGE-1", "name": "Platform 1"}],
    "competition_id": "COMP-1",
    "force_token_invalid": False,
    "unreachable": False,
}


@app.post("/account/login")
async def login(request: Request):
    if STATE["unreachable"]:
        return Response(status_code=503)
    raw = (await request.body()).decode("utf-8", errors="replace")
    parsed = parse_qs(raw)
    identity = (parsed.get("identity") or [None])[0]
    credential = (parsed.get("credential") or [None])[0]
    if (identity, credential) != ("u", STATE["credentials"]["u"]):
        return Response(status_code=401)
    return Response(
        status_code=200,
        headers={"set-cookie": "VPORTAL=fake-cookie; Path=/; HttpOnly"},
    )


@app.get("/auth/token")
async def token(request: Request):
    if request.headers.get("cookie", "").find("VPORTAL=fake-cookie") == -1:
        return Response(status_code=401)
    return JSONResponse({"access_token": "fake-jwt", "exp": 9999999999})


@app.post("/graphql")
async def graphql(request: Request):
    if STATE["unreachable"]:
        return Response(status_code=503)
    auth = request.headers.get("authorization", "")
    if STATE["force_token_invalid"] or auth != "Bearer fake-jwt":
        return Response(status_code=401)
    body = await request.json()
    query = body.get("query", "")
    if "profile" in query:
        return JSONResponse({"data": {"profile": {"competition": {"id": STATE["competition_id"]}}}})
    if "competitionStageList" in query:
        return JSONResponse({"data": {"competitionStageList": {
            "competitionStages": STATE["stages"]
        }}})
    if "competitionGroupList" in query:
        return JSONResponse({"data": {"competitionGroupList": {
            "competitionGroups": [{"id": "G-1", "name": "Flight A", "active": True}]
        }}})
    if "competitionAthleteAttemptList" in query:
        return JSONResponse({"data": {"competitionAthleteAttemptList": {
            "competitionAthleteAttempts": [STATE["active_attempt"]] if STATE["active_attempt"] else [],
        }}})
    return JSONResponse({"errors": [{"message": "unknown query"}]}, status_code=400)
