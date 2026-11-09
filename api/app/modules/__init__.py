"""Module registry: every feature in the hub is listed here so the dashboard can render tiles.

To add a module, give it a package under app/modules/, include its router in app/main.py and
list it here. The list is in priority order: the home screen shows tiles in this order.
"""

from typing import Literal

from pydantic import BaseModel

# The home-screen folder a module starts in (none: on the home screen itself); people can move
# it from there.
Folder = Literal["games"]


class ModuleInfo(BaseModel):
    id: str
    name: str
    description: str
    icon: str
    path: str
    folder: Folder | None = None
    # Only shown to the hub's owner.
    owner_only: bool = False


MODULES: list[ModuleInfo] = [
    ModuleInfo(
        id="trading",
        name="Trading",
        description="Index levels from your analyses, live IG prices and alerts near a level.",
        icon="📉",
        path="/trading",
        owner_only=True,
    ),
    ModuleInfo(
        id="economy",
        name="Economy",
        description="Net worth, subscriptions and purchase rules before you buy.",
        icon="💰",
        path="/economy",
        owner_only=True,
    ),
    ModuleInfo(
        id="files",
        name="Files",
        description="Shared and private folders: send from the phone, grab it on the laptop.",
        icon="📁",
        path="/files",
    ),
    ModuleInfo(
        id="network",
        name="Network",
        description="Who's on the Wi-Fi, internet speed and uptime, and how the Pi is doing.",
        icon="📶",
        path="/network",
    ),
    ModuleInfo(
        id="security",
        name="Security",
        description="Away access, signed-in devices and the weekly check of the hub and Pi.",
        icon="🔒",
        path="/security",
        owner_only=True,
    ),
    ModuleInfo(
        id="plants",
        name="Plants",
        description="The plan for sensors and self-watering, one microcontroller per plant.",
        icon="🌱",
        path="/plants",
    ),
    ModuleInfo(
        id="poker",
        name="Poker",
        description="Pre-flop equity, hand calculator and home-game settle-up.",
        icon="♠️",
        path="/poker",
        folder="games",
    ),
    ModuleInfo(
        id="tetris",
        name="Tetris",
        description="Solo or against everyone on the Wi-Fi, with a few power-ups.",
        icon="🧱",
        path="/tetris",
        folder="games",
    ),
]
