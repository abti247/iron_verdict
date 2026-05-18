"""Thin proxy to VPortal — see docs/superpowers/specs/2026-05-13-vportal-integration-design.md."""

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
    "staging.vportal-online.de",
}
_TEST_HOSTS = {"localhost", "127.0.0.1"}


def _allowed_hosts() -> set[str]:
    if settings.TEST_MODE:
        return _PRODUCTION_HOSTS | _TEST_HOSTS
    return _PRODUCTION_HOSTS


def _validate_host(host: str) -> None:
    if host not in _allowed_hosts():
        logger.warning("vportal_host_rejected", extra={"host": host})
        raise HTTPException(status_code=400, detail=f"Host not in allowlist: {host}")


_ALLOWED_TOP_LEVEL_FIELDS = {
    "profile",                          # profile.competition.id
    "competitionStageList",
    "competitionGroupList",
    "competitionAthleteAttemptList",
}

_MUTATION_RE = re.compile(r"^\s*mutation\b", re.IGNORECASE)


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
    raise HTTPException(status_code=501, detail="not implemented yet")


@router.post("/graphql")
async def graphql(body: GraphQLRequest):
    _validate_host(body.host)
    _validate_graphql_query(body.query)
    raise HTTPException(status_code=501, detail="not implemented yet")
