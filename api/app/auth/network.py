"""Trust the home network: anything on a private address may use the hub, nothing else may."""

import ipaddress
from functools import lru_cache

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.config import get_settings

Network = ipaddress.IPv4Network | ipaddress.IPv6Network


@lru_cache
def _networks(spec: tuple[str, ...]) -> tuple[Network, ...]:
    return tuple(ipaddress.ip_network(n, strict=False) for n in spec)


def is_trusted(host: str | None) -> bool:
    if not host:
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return any(ip in net for net in _networks(tuple(get_settings().trusted_networks)))


class LocalNetworkOnly(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # request.client is the real device: Caddy sets X-Forwarded-For and uvicorn
        # (--proxy-headers) applies it. Caddy ignores any X-Forwarded-For a client sends.
        if not is_trusted(request.client.host if request.client else None):
            return JSONResponse(
                {"detail": "Blueberry Home only answers devices on your home network"},
                status_code=403,
            )
        return await call_next(request)
