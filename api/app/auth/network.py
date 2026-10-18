"""Trust the home network: anything on a private address may use the hub, nothing else may.

The one exception is away access: while an admin has it on, devices on the VPN's addresses are
let in too, but only ones that already joined at home (see is_away).

Being on the home network isn't enough on its own, because a website open on a phone at home
also sends its requests from that phone. Two more checks keep websites out:
- DNS rebinding: a website's owner can point its name at the Pi's address, so its pages would
  reach the hub from inside the house. The hub only answers to names nobody can register on
  the internet (hub.home, raspberrypi.local, an IP address, ...), see host_allowed.
- Cross-site requests: a website can't read the hub's answers, but it could still send it a
  POST (delete a file, join as a device). Browsers say where a request came from, so changes
  are refused unless they come from the hub's own pages, see cross_site."""

import ipaddress
from functools import lru_cache
from urllib.parse import urlsplit

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


# Names under these can't be bought, so nobody outside can point one at the Pi.
LOCAL_SUFFIXES = (
    ".home",
    ".lan",
    ".local",
    ".localdomain",
    ".localhost",
    ".internal",
    ".home.arpa",
    ".ts.net",
)
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def _hostname(host_header: str) -> str:
    host = host_header.strip().lower()
    if host.startswith("["):
        return host[1 : host.find("]")] if "]" in host else host
    if host.count(":") == 1:
        host = host.split(":")[0]
    return host.rstrip(".")


def host_allowed(host_header: str | None) -> bool:
    """Whether the Host a request was sent to is one of the hub's own names."""
    if not host_header:
        return True  # not a browser: browsers always send Host
    name = _hostname(host_header)
    if _ip(name) is not None or "." not in name:
        return True  # an address, or a single-label name like "raspberrypi" or "localhost"
    if name.endswith(LOCAL_SUFFIXES):
        return True
    return name in {h.lower().rstrip(".") for h in get_settings().allowed_hosts}


def cross_site(method: str, headers) -> bool:
    """True for a change (POST, PUT, ...) a browser sent from some other website's page."""
    if method.upper() in SAFE_METHODS:
        return False
    if headers.get("sec-fetch-site") == "cross-site":
        return True
    origin = headers.get("origin")
    if origin is None:
        return False  # not a browser, or an old one that sends neither header
    return (
        origin == "null" or urlsplit(origin).netloc.lower() != (headers.get("host") or "").lower()
    )


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
        if not host_allowed(request.headers.get("host")):
            tracker.record("blocked", host, f"{request.url.path} (as {request.headers['host']})")
            return JSONResponse(
                {"detail": "Blueberry Home doesn't answer to that name"}, status_code=403
            )
        if cross_site(request.method, request.headers):
            tracker.record("blocked", host, f"{request.url.path} (from another website)")
            return JSONResponse(
                {"detail": "Changes can only be made from Blueberry Home's own pages"},
                status_code=403,
            )
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
