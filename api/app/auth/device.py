"""Starting names for new devices. A browser can't read a MAC address (and phones randomise
theirs per network anyway), so the name comes from what the router calls the device, if it
answers a reverse DNS lookup, or else from the browser's user agent."""

import re
import secrets
import socket
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout

_lookups = ThreadPoolExecutor(max_workers=2, thread_name_prefix="rdns")

_ANDROID_MODEL = re.compile(
    r"Android[^;)]*;\s*(?:[a-z]{2}[-_][a-zA-Z]{2};\s*)?([^;)]+?)(?:\s+Build/|\))"
)


def device_from_user_agent(ua: str | None) -> str:
    ua = ua or ""
    if "iPhone" in ua:
        return "iPhone"
    if "iPad" in ua:
        return "iPad"
    if "Android" in ua:
        match = _ANDROID_MODEL.search(ua)
        model = match.group(1).strip() if match else ""
        # Chrome's reduced user agent reports the model as "K".
        if model and model != "K" and len(model) > 1:
            return model
        return "Android tablet" if "Mobile" not in ua else "Android phone"
    if "CrOS" in ua:
        return "Chromebook"
    if "Macintosh" in ua:
        return "Mac"
    if "Windows" in ua:
        return "Windows PC"
    if "Linux" in ua:
        return "Linux PC"
    return "Device"


def router_name(ip: str | None, timeout: float = 0.5) -> str | None:
    """The hostname the router hands out for this address (e.g. "Nils-iPhone"), if any."""
    if not ip:
        return None
    try:
        host = _lookups.submit(socket.gethostbyaddr, ip).result(timeout=timeout)[0]
    except (OSError, FutureTimeout):
        return None
    name = host.split(".")[0]
    if (
        not name
        or name.lower() in {"localhost", "gateway", "host"}
        or re.fullmatch(r"[\d-]+", name)
    ):
        return None
    if "docker" in name.lower():
        return None
    return name[:64]


def new_username(label: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")[:26] or "device"
    return f"{slug}-{secrets.token_hex(2)}"
