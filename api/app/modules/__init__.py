"""Module registry: every feature in the hub is listed here so the dashboard can render tiles.

A module with status "planned" shows on the dashboard as coming soon. When a module is built,
give it a package under app/modules/, include its router in app/main.py and set it "ready".
"""

from typing import Literal

from pydantic import BaseModel

Status = Literal["ready", "planned"]
# The home-screen folder a module starts in; people can move it from there.
Folder = Literal["games", "learning", "nerd", "life"]


class ModuleInfo(BaseModel):
    id: str
    name: str
    description: str
    icon: str
    path: str
    status: Status
    phase: int
    folder: Folder
    # Only shown to the hub's owner.
    owner_only: bool = False


MODULES: list[ModuleInfo] = [
    ModuleInfo(
        id="french",
        name="French",
        description="Lessons, spaced-repetition review and listening practice.",
        icon="🇫🇷",
        path="/learn/french",
        status="ready",
        phase=1,
        folder="learning",
    ),
    ModuleInfo(
        id="mandarin",
        name="Mandarin",
        description="Pinyin, tones and characters, with Singapore everyday phrases.",
        icon="🇸🇬",
        path="/learn/mandarin",
        status="ready",
        phase=1,
        folder="learning",
    ),
    ModuleInfo(
        id="assistant",
        name="Assistant",
        description="Chat with a small language model running on the Pi.",
        icon="🤖",
        path="/assistant",
        status="ready",
        phase=0,
        folder="nerd",
    ),
    ModuleInfo(
        id="poker",
        name="Poker",
        description="Pre-flop equity, hand calculator and home-game settle-up.",
        icon="♠️",
        path="/poker",
        status="ready",
        phase=2,
        folder="games",
    ),
    ModuleInfo(
        id="files",
        name="Files",
        description="Shared and private folders: send from the phone, grab it on the laptop.",
        icon="📁",
        path="/files",
        status="ready",
        phase=3,
        folder="life",
    ),
    ModuleInfo(
        id="security",
        name="Security",
        description="Away access, signed-in devices and the weekly check of the hub and Pi.",
        icon="🔒",
        path="/security",
        status="ready",
        phase=3,
        folder="nerd",
        owner_only=True,
    ),
    ModuleInfo(
        id="network",
        name="Network",
        description="Who's on the Wi-Fi, internet speed and uptime, and how the Pi is doing.",
        icon="📶",
        path="/network",
        status="ready",
        phase=3,
        folder="nerd",
    ),
    ModuleInfo(
        id="tetris",
        name="Tetris",
        description="Solo or against everyone on the Wi-Fi, with a few power-ups.",
        icon="🧱",
        path="/tetris",
        status="ready",
        phase=4,
        folder="games",
    ),
    ModuleInfo(
        id="finance",
        name="Finance",
        description="Budgets, portfolio and net worth, kept on the Pi.",
        icon="📈",
        path="/finance",
        status="planned",
        phase=6,
        folder="life",
    ),
    ModuleInfo(
        id="plants",
        name="Plants",
        description="Watering schedules, care log and moisture sensors.",
        icon="🪴",
        path="/plants",
        status="planned",
        phase=6,
        folder="life",
    ),
    ModuleInfo(
        id="reading",
        name="Reading",
        description="Books, notes and highlights that become review cards.",
        icon="📚",
        path="/reading",
        status="planned",
        phase=6,
        folder="learning",
    ),
    ModuleInfo(
        id="wow",
        name="WoW",
        description="Characters, weekly vault, Mythic+ and auction prices.",
        icon="⚔️",
        path="/wow",
        status="planned",
        phase=6,
        folder="games",
    ),
]
