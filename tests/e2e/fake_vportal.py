"""Tiny FastAPI app that mimics the subset of VPortal Iron Verdict consumes."""

import base64
import json

from fastapi import FastAPI, Form, Request
from fastapi.responses import JSONResponse, Response

app = FastAPI()


def _make_jwt(exp: int) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').decode().rstrip("=")
    payload = base64.urlsafe_b64encode(json.dumps({"exp": exp}).encode()).decode().rstrip("=")
    return f"{header}.{payload}.fake-signature"


# Real-JWT-shaped token. Mirrors real VPortal in that `exp` is inside the JWT,
# not in the top-level `/auth/token` response envelope.
FAKE_JWT = _make_jwt(9999999999)


STATE = {
    "credentials": {"u": "p"},
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
async def login(
    request: Request,
    identity: str | None = Form(None),
    credential: str | None = Form(None),
):
    if STATE["unreachable"]:
        return Response(status_code=503)
    # Real referee/VPortal traffic is multipart/form-data. Anything else means
    # a regression in our proxy; reject loudly so it fails the test.
    content_type = request.headers.get("content-type", "")
    if not content_type.startswith("multipart/form-data"):
        return Response(status_code=415)
    if (identity, credential) != ("u", STATE["credentials"]["u"]):
        return Response(status_code=401)
    # 302 + Set-Cookie + Location stress-tests two things at once:
    # status-code tolerance in the proxy (referee ignores the code) and
    # Set-Cookie parsing of the comma inside expires=...
    return Response(
        status_code=302,
        headers={
            "set-cookie": "VPORTAL=fake-cookie; expires=Wed, 21 Oct 2099 07:28:00 GMT; Path=/; HttpOnly",
            "location": "/dashboard",
        },
    )


@app.get("/auth/token")
async def token(request: Request):
    if "VPORTAL=fake-cookie" not in request.headers.get("cookie", ""):
        return Response(status_code=401)
    # No top-level exp — mirrors real VPortal; the proxy must decode the JWT.
    return JSONResponse({"access_token": FAKE_JWT})


@app.post("/graphql")
async def graphql(request: Request):
    if STATE["unreachable"]:
        return Response(status_code=503)
    auth = request.headers.get("authorization", "")
    if STATE["force_token_invalid"] or auth != f"Bearer {FAKE_JWT}":
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


@app.post("/_control/force_token_invalid")
async def _force_token_invalid():
    STATE["force_token_invalid"] = True
    return {"ok": True}


@app.post("/_control/reset")
async def _reset():
    STATE["force_token_invalid"] = False
    STATE["unreachable"] = False
    return {"ok": True}


@app.post("/_control/unreachable")
async def _unreachable():
    STATE["unreachable"] = True
    return {"ok": True}


@app.post("/_control/clear_attempt")
async def _clear_attempt():
    STATE["active_attempt"] = None
    return {"ok": True}


@app.post("/_control/restore_attempt")
async def _restore_attempt():
    STATE["active_attempt"] = {
        "id": "A-1", "attempt": 2, "discipline": "SQUAT", "weight": 215, "status": None,
        "competitionAthlete": {
            "firstName": "Maria", "lastName": "Schneider",
            "club": {"name": "SV Eisenkraft Berlin"},
            "bodyWeightCategory": {"name": "-72 kg"},
            "ageCategory": {"name": "Open"},
        },
    }
    return {"ok": True}
