"""Thin, stateless proxy to VPortal — host- and operation-allowlisted, pull-only."""

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


_SESSION_COOKIE_NAMES = ("__Host-VPORTAL", "VPORTAL")


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


def _make_login_client() -> httpx.AsyncClient:
    """Fresh httpx client per login flow.

    Why: httpx.AsyncClient keeps a cookie jar that persists across requests
    on the same instance. If the shared `_http_client` were used for login,
    a still-valid VPORTAL cookie from a previous operator's login would be
    sent on the new login's outbound request — real VPortal would treat it
    as a session refresh, ignore the form credentials, and return a fresh
    cookie/JWT for the *previous* operator. A user typing garbage credentials
    would inherit the prior session. Scoping cookies to one login flow
    closes that leak.
    """
    return httpx.AsyncClient(timeout=5.0)


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


# Why 424 for upstream failures on /login (issue #100): Cloudflare in front of
# the deployment replaces the body of an origin 502 with its own error page, so
# the reason never reached the operator's dialog. A non-5xx status passes
# through unchanged. `reason` is a fixed code the frontend maps to a message.
_LOGIN_UPSTREAM_FAILED = 424


def _login_failed(host: str, reason: str, *, detail_extra: dict | None = None, **log_fields) -> HTTPException:
    """Log one structured warning for a failed login and build the HTTP error.

    Callers pass only statuses, header values and cookie *names* — never cookie
    values, credentials or response bodies.
    """
    logger.warning("vportal_login_failed", extra={"reason": reason, "host": host, **log_fields})
    return HTTPException(
        status_code=_LOGIN_UPSTREAM_FAILED,
        detail={"reason": reason, **(detail_extra or {})},
    )


@router.post("/login")
async def login(body: LoginRequest):
    _validate_host(body.host)
    base = _base_url(body.host)

    # Fresh client per login — see _make_login_client docstring for why
    # the shared client would otherwise leak cookies between operators.
    async with _make_login_client() as http:
        # Step 1: multipart-POST /account/login. Status code is intentionally
        # not inspected — real VPortal returns a pre-auth session cookie even
        # for wrong credentials (verified at staging 2026-05-19), and the
        # actual auth check happens at /auth/token. Cookie presence is the
        # success signal for "the form was processed," not "the credentials
        # were valid."
        try:
            login_resp = await http.post(
                f"{base}/account/login",
                files={
                    "identity": (None, body.identity),
                    "credential": (None, body.credential),
                },
                headers={"Accept-Language": "de"},
                follow_redirects=False,
            )
        except httpx.TransportError as exc:
            raise _login_failed(
                body.host, "unreachable",
                upstream_path="/account/login", error=type(exc).__name__,
            )

        login_log = {
            "login_status": login_resp.status_code,
            "login_location": login_resp.headers.get("location"),
            "cookie_names": sorted(login_resp.cookies.keys()),
        }

        # Use httpx's parsed cookies rather than splitting Set-Cookie on commas —
        # the standard cookielib parser handles commas inside expires=... correctly.
        # VPortal renamed the cookie VPORTAL -> __Host-VPORTAL (seen at staging
        # 2026-10-13, issue #101); accept both so login keeps working whenever
        # production switches, and send it back under the name it arrived with.
        for vportal_cookie_name in _SESSION_COOKIE_NAMES:
            vportal_cookie_value = login_resp.cookies.get(vportal_cookie_name)
            if vportal_cookie_value:
                break
        else:
            raise _login_failed(body.host, "no_session_cookie", **login_log)

        # Step 2: GET /auth/token with the cookie. This is where VPortal
        # validates the underlying credentials — a pre-auth cookie issued
        # for wrong credentials gets rejected here with 401/403.
        try:
            token_resp = await http.get(
                f"{base}/auth/token",
                headers={
                    "cookie": f"{vportal_cookie_name}={vportal_cookie_value}",
                    "Accept-Language": "de",
                },
            )
        except httpx.TransportError as exc:
            raise _login_failed(
                body.host, "unreachable",
                upstream_path="/auth/token", error=type(exc).__name__, **login_log,
            )

        token_log = {
            **login_log,
            "token_status": token_resp.status_code,
            "token_location": token_resp.headers.get("location"),
            "content_type": token_resp.headers.get("content-type"),
        }

        # Treat redirects and 4xx-class statuses on /auth/token as auth
        # failures. Real VPortal returns 302 (redirect back to /login) when
        # the pre-auth cookie can't be exchanged — verified at staging
        # 2026-05-19. 401/403 covered for defensive completeness.
        if token_resp.status_code in (302, 401, 403):
            # Info, not warning: usually just a mistyped password. Logged because
            # a missing role may look the same to us (issue #100); the redirect
            # target is what tells the two apart.
            logger.info("vportal_login_rejected", extra={"host": body.host, **token_log})
            raise HTTPException(status_code=401, detail="Invalid VPortal credentials")
        if token_resp.status_code != 200:
            raise _login_failed(
                body.host, "token_exchange_failed",
                detail_extra={"upstream_status": token_resp.status_code}, **token_log,
            )

        try:
            token_payload = token_resp.json()
        except ValueError:
            token_payload = None
        access_token = token_payload.get("access_token") if isinstance(token_payload, dict) else None
        if not access_token:
            raise _login_failed(body.host, "missing_access_token", **token_log)

        return {
            "access_token": access_token,
            "exp": _extract_jwt_exp(access_token) or token_payload.get("exp"),
            "fetch_interval_ms": settings.VPORTAL_FETCH_INTERVAL_MS,
        }


@router.post("/graphql")
async def graphql(body: GraphQLRequest):
    _validate_host(body.host)
    _validate_graphql_query(body.query)

    # Why one retry on transport errors: the shared client pools keep-alive
    # connections, and VPortal or a NAT/load balancer may close an idle one
    # before the next poll reuses it (seen live 2026-05-23 as a single
    # RemoteProtocolError between successful polls). httpx drops the dead
    # connection, so the retry opens a fresh one. Safe because the allowlist
    # above makes every forwarded operation a read. No delay before the retry:
    # the failure is a stale connection, not an overloaded upstream.
    for attempt in (1, 2):
        try:
            upstream = await _http_client.post(
                f"{_base_url(body.host)}/graphql",
                json={"query": body.query, "variables": body.variables or {}},
                headers={
                    "Authorization": f"Bearer {body.token}",
                    "content-type": "application/json",
                    "Accept-Language": "de",
                },
            )
            break
        except httpx.TransportError as exc:
            if attempt == 2:
                logger.warning(
                    "vportal_upstream_unreachable",
                    extra={"host": body.host, "error": type(exc).__name__},
                )
                raise HTTPException(status_code=502, detail="VPortal upstream unreachable")
            # Logged although the retry usually succeeds: shows in the field
            # how often and when pooled connections go stale.
            logger.info(
                "vportal_transport_retry",
                extra={"host": body.host, "error": type(exc).__name__},
            )

    if upstream.status_code == 401:
        raise HTTPException(status_code=401, detail="VPortal token rejected")
    if upstream.status_code >= 500:
        raise HTTPException(status_code=502, detail="VPortal upstream error")

    return upstream.json()
