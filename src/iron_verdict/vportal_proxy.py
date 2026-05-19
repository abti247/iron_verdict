"""Thin proxy to VPortal — see docs/superpowers/specs/2026-05-13-vportal-integration-design.md."""

import base64
import json
import logging
import re

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from iron_verdict.config import settings

logger = logging.getLogger("iron_verdict")

_PRODUCTION_HOSTS = {
    "bvdk.vportal-online.de",
    "oevk.vportal-online.de",
    # Federation-prefixed staging instances. Same DNS zone as production but
    # gated by separate operator credentials. Surfaced in the UI only when
    # EXPOSE_VPORTAL_STAGING=1; allowlisted unconditionally because no-one
    # can log in without staging credentials anyway.
    "staging-bvdk.vportal-online.de",
    "staging-oevk.vportal-online.de",
}
_TEST_HOSTS = {"localhost", "127.0.0.1"}


def _allowed_hosts() -> set[str]:
    if settings.TEST_MODE:
        return _PRODUCTION_HOSTS | _TEST_HOSTS
    return _PRODUCTION_HOSTS


def _base_url(host: str) -> str:
    if settings.TEST_MODE and (host.startswith("127.0.0.1") or host.startswith("localhost")):
        return f"http://{host}"
    return f"https://{host}"


def _validate_host(host: str) -> None:
    if host in _allowed_hosts():
        return
    if settings.TEST_MODE and (host.startswith("127.0.0.1:") or host.startswith("localhost:")):
        return
    logger.warning("vportal_host_rejected", extra={"host": host})
    raise HTTPException(status_code=400, detail=f"Host not in allowlist: {host}")


_ALLOWED_TOP_LEVEL_FIELDS = {
    "profile",                          # profile.competition.id
    "competitionStageList",
    "competitionGroupList",
    "competitionAthleteAttemptList",
}

_MUTATION_RE = re.compile(r"^\s*mutation\b", re.IGNORECASE)

_http_client: httpx.AsyncClient = httpx.AsyncClient(timeout=5.0)


def _extract_jwt_exp(token: str) -> int | None:
    """Decode the JWT payload segment and return the `exp` claim, if any.

    Why: real VPortal does not include `exp` at the top level of the /auth/token
    response (referee reads it from the JWT itself). Keep a top-level fallback
    in the caller so this stays robust if a future VPortal release adds it back.
    """
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return None
        payload_b64 = parts[1]
        padding = "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64 + padding))
        exp = payload.get("exp")
        return int(exp) if isinstance(exp, (int, float)) else None
    except Exception:
        return None


def _validate_graphql_query(query: str) -> None:
    if _MUTATION_RE.match(query):
        raise HTTPException(status_code=400, detail="Mutation operations are not permitted; this proxy is read-only.")
    # Find the first top-level field name after the outer '{'
    body = query.strip()
    if body.startswith("query"):
        # Strip 'query Name($args: Type) {'
        brace = body.find("{")
        if brace == -1:
            raise HTTPException(status_code=400, detail="Malformed GraphQL operation.")
        body = body[brace + 1:]
    elif body.startswith("{"):
        body = body[1:]
    else:
        raise HTTPException(status_code=400, detail="Malformed GraphQL operation.")
    m = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)", body)
    if not m or m.group(1) not in _ALLOWED_TOP_LEVEL_FIELDS:
        first_field = m.group(1) if m else "<none>"
        logger.warning("vportal_operation_rejected", extra={"first_field": first_field})
        raise HTTPException(status_code=400, detail=f"Operation not in allowlist: {first_field}")


router = APIRouter(prefix="/api/vportal", tags=["vportal"])


class LoginRequest(BaseModel):
    host: str
    identity: str
    credential: str


class GraphQLRequest(BaseModel):
    host: str
    token: str
    query: str
    variables: dict | None = None


@router.post("/login")
async def login(body: LoginRequest):
    _validate_host(body.host)
    base = _base_url(body.host)

    # Step 1: multipart-POST /account/login. Status code is intentionally not
    # inspected — referee doesn't either, and real VPortal may redirect (302)
    # on success. Cookie presence is the success signal.
    #
    # Wrong-credentials UX caveat: bad creds will surface as 502 "no session
    # cookie" rather than 401 until we capture real VPortal's wrong-creds
    # response shape during staging (see docs/vportal-fake-server-fidelity-followups.md).
    login_resp = await _http_client.post(
        f"{base}/account/login",
        files={
            "identity": (None, body.identity),
            "credential": (None, body.credential),
        },
        headers={"Accept-Language": "de"},
        follow_redirects=False,
    )

    # Use httpx's parsed cookies rather than splitting Set-Cookie on commas —
    # the standard cookielib parser handles commas inside expires=... correctly.
    vportal_cookie_value = login_resp.cookies.get("VPORTAL")
    if not vportal_cookie_value:
        raise HTTPException(status_code=502, detail="VPortal did not return a session cookie")

    # Step 2: GET /auth/token with the parsed cookie value
    token_resp = await _http_client.get(
        f"{base}/auth/token",
        headers={
            "cookie": f"VPORTAL={vportal_cookie_value}",
            "Accept-Language": "de",
        },
    )
    if token_resp.status_code != 200:
        raise HTTPException(status_code=502, detail="VPortal token exchange failed")

    token_payload = token_resp.json()
    access_token = token_payload.get("access_token")
    if not access_token:
        raise HTTPException(status_code=502, detail="VPortal token response missing access_token")

    return {
        "access_token": access_token,
        "exp": _extract_jwt_exp(access_token) or token_payload.get("exp"),
        "fetch_interval_ms": settings.VPORTAL_FETCH_INTERVAL_MS,
    }


@router.post("/graphql")
async def graphql(body: GraphQLRequest):
    _validate_host(body.host)
    _validate_graphql_query(body.query)

    upstream = await _http_client.post(
        f"{_base_url(body.host)}/graphql",
        json={"query": body.query, "variables": body.variables or {}},
        headers={
            "Authorization": f"Bearer {body.token}",
            "content-type": "application/json",
            "Accept-Language": "de",
        },
    )

    if upstream.status_code == 401:
        raise HTTPException(status_code=401, detail="VPortal token rejected")
    if upstream.status_code >= 500:
        raise HTTPException(status_code=502, detail="VPortal upstream error")

    return upstream.json()
