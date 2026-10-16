"""Trust the home network: anything on a private address may use the hub, nothing else may.

The one exception is away access: while an admin has it on, devices on the VPN's addresses are
let in too, but only ones that already joined at home (see is_away)."""

import ipaddress
from functools import lru_cache

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.config import get_settings
from app.modules.security import tracker
from app.modules.security.remote import away_enabled

Network = ipaddress.IPv4Network | ipaddress.IPv6Network


@lru_cache
def _networks(spec: tuple[str, ...]) -> tuple[Network, ...]:
    return tuple(ipaddress.ip_network(n, strict=False) for n in spec)


def _ip(host: str | None) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    if not host:
        return None
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return None
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip


def _in(host: str | None, spec: list[str]) -> bool:
    ip = _ip(host)
    return ip is not None and any(ip in net for net in _networks(tuple(spec)))


def is_trusted(host: str | None) -> bool:
    return _in(host, get_settings().trusted_networks)


def is_away_network(host: str | None) -> bool:
    return not is_trusted(host) and _in(host, get_settings().away_networks)


def is_public(host: str | None) -> bool:
    """A real internet address, as opposed to home, VPN or loopback ones."""
    ip = _ip(host)
    return ip is not None and ip.is_global


def is_away(request: Request) -> bool:
    return getattr(request.state, "away", False)


def require_home(request: Request) -> None:
    """For things that should only happen in the house: joining, setup, logging in."""
    if is_away(request):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Do this at home: away access only lets in devices that already joined on the Wi-Fi",
        )


class LocalNetworkOnly(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # request.client is the real device: Caddy sets X-Forwarded-For and uvicorn
        # (--proxy-headers) applies it. Caddy ignores any X-Forwarded-For a client sends.
        host = request.client.host if request.client else None
        request.state.away = False
        if is_trusted(host):
            return await call_next(request)
        if is_away_network(host):
            if await run_in_threadpool(away_enabled):
                request.state.away = True
                tracker.record("away", host, request.url.path)
                return await call_next(request)
            tracker.record("blocked", host, request.url.path)
            return JSONResponse(
                {"detail": "Away access is off. Turn it on at home under Security."},
                status_code=403,
            )
        tracker.record("blocked", host, request.url.path)
        return JSONResponse(
            {"detail": "Blueberry Home only answers devices on your home network"},
            status_code=403,
        )
