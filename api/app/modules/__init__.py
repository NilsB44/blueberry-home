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


MODULES: list[ModuleInfo] = [
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
        id="french",
        name="French",
        description="Lessons, spaced-repetition review and listening practice.",
        icon="🇫🇷",
        path="/learn/french",
        status="planned",
        phase=1,
    ),
    ModuleInfo(
        id="poker",
        name="Poker",
        description="Pre-flop equity, hand calculator and home-game settle-up.",
        icon="♠️",
        path="/poker",
        status="planned",
        phase=2,
    ),
    ModuleInfo(
        id="files",
        name="Files",
        description="Shared folders and a phone-to-laptop drop zone.",
        icon="📁",
        path="/files",
        status="planned",
        phase=3,
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
        description="Multiplayer Tetris over the local network.",
        icon="🧱",
        path="/tetris",
        status="planned",
        phase=4,
    ),
    ModuleInfo(
        id="mandarin",
        name="Mandarin",
        description="Pinyin, tones, characters and HSK vocabulary.",
        icon="🇸🇬",
        path="/learn/mandarin",
        status="planned",
        phase=5,
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
