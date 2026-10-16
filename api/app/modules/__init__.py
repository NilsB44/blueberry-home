"""Module registry: every feature in the hub is listed here so the dashboard can render tiles.

A module with status "planned" shows on the dashboard as coming soon. When a module is built,
give it a package under app/modules/, include its router in app/main.py and set it "ready".
"""

from typing import Literal

from pydantic import BaseModel

Status = Literal["ready", "planned"]


class ModuleInfo(BaseModel):
    id: str
    name: str
    description: str
    icon: str
    path: str
    status: Status
    phase: int
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
    ),
    ModuleInfo(
        id="mandarin",
        name="Mandarin",
        description="Pinyin, tones and characters, with Singapore everyday phrases.",
        icon="🇸🇬",
        path="/learn/mandarin",
        status="ready",
        phase=1,
    ),
    ModuleInfo(
        id="assistant",
        name="Assistant",
        description="Chat with a small language model running on the Pi.",
        icon="🤖",
        path="/assistant",
        status="ready",
        phase=0,
    ),
    ModuleInfo(
        id="poker",
        name="Poker",
        description="Pre-flop equity, hand calculator and home-game settle-up.",
        icon="♠️",
        path="/poker",
        status="ready",
        phase=2,
    ),
    ModuleInfo(
        id="files",
        name="Files",
        description="Shared and private folders: send from the phone, grab it on the laptop.",
        icon="📁",
        path="/files",
        status="ready",
        phase=3,
    ),
    ModuleInfo(
        id="security",
        name="Security",
        description="Away access, signed-in devices and the weekly check of the hub and Pi.",
        icon="🔒",
        path="/security",
        status="ready",
        phase=3,
        owner_only=True,
    ),
    ModuleInfo(
        id="claude",
        name="Claude",
        description="Tokens used per day, averages, models and what it would cost on the API.",
        icon="✳️",
        path="/claude",
        status="ready",
        phase=3,
        owner_only=True,
    ),
    ModuleInfo(
        id="network",
        name="Network",
        description="Devices on the Wi-Fi, ad blocking stats and VPN status.",
        icon="🛡️",
        path="/network",
        status="planned",
        phase=3,
    ),
    ModuleInfo(
        id="tetris",
        name="Tetris",
        description="Solo or against everyone on the Wi-Fi, with a few power-ups.",
        icon="🧱",
        path="/tetris",
        status="ready",
        phase=4,
    ),
    ModuleInfo(
        id="finance",
        name="Finance",
        description="Budgets, portfolio and net worth, kept on the Pi.",
        icon="📈",
        path="/finance",
        status="planned",
        phase=6,
    ),
    ModuleInfo(
        id="plants",
        name="Plants",
        description="Watering schedules, care log and moisture sensors.",
        icon="🪴",
        path="/plants",
        status="planned",
        phase=6,
    ),
    ModuleInfo(
        id="reading",
        name="Reading",
        description="Books, notes and highlights that become review cards.",
        icon="📚",
        path="/reading",
        status="planned",
        phase=6,
    ),
    ModuleInfo(
        id="wow",
        name="WoW",
        description="Characters, weekly vault, Mythic+ and auction prices.",
        icon="⚔️",
        path="/wow",
        status="planned",
        phase=6,
    ),
]
