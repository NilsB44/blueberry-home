"""Module registry: every feature in the hub is listed here so the dashboard can render tiles.

To add a module, give it a package under app/modules/, include its router in app/main.py and
list it here.
"""

from typing import Literal

from pydantic import BaseModel

# The home-screen folder a module starts in; people can move it from there.
Folder = Literal["games", "nerd", "life"]


class ModuleInfo(BaseModel):
    id: str
    name: str
    description: str
    icon: str
    path: str
    folder: Folder
    # Only shown to the hub's owner.
    owner_only: bool = False


MODULES: list[ModuleInfo] = [
    ModuleInfo(
        id="poker",
        name="Poker",
        description="Pre-flop equity, hand calculator and home-game settle-up.",
        icon="♠️",
        path="/poker",
        folder="games",
    ),
    ModuleInfo(
        id="files",
        name="Files",
        description="Shared and private folders: send from the phone, grab it on the laptop.",
        icon="📁",
        path="/files",
        folder="life",
    ),
    ModuleInfo(
        id="security",
        name="Security",
        description="Away access, signed-in devices and the weekly check of the hub and Pi.",
        icon="🔒",
        path="/security",
        folder="nerd",
        owner_only=True,
    ),
    ModuleInfo(
        id="network",
        name="Network",
        description="Who's on the Wi-Fi, internet speed and uptime, and how the Pi is doing.",
        icon="📶",
        path="/network",
        folder="nerd",
    ),
    ModuleInfo(
        id="tetris",
        name="Tetris",
        description="Solo or against everyone on the Wi-Fi, with a few power-ups.",
        icon="🧱",
        path="/tetris",
        folder="games",
    ),
    ModuleInfo(
        id="trading",
        name="Trading",
        description="Index levels from your analyses, live IG prices and alerts near a level.",
        icon="📉",
        path="/trading",
        folder="life",
        owner_only=True,
    ),
]
