"""Thin proxy to VPortal — see docs/superpowers/specs/2026-05-13-vportal-integration-design.md."""

import logging

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
    raise HTTPException(status_code=501, detail="not implemented yet")
