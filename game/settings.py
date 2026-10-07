"""Persistent player settings, stored as JSON next to the game."""

import getpass
import json
import os
from dataclasses import dataclass, field

SETTINGS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")

RESOLUTION_PRESETS = [
    (1024, 768),
    (1280, 720),
    (1366, 768),
    (1600, 900),
    (1920, 1080),
    (2560, 1440),
    (3840, 2160),
]
DEFAULT_RESOLUTION = (1280, 720)
MIN_RESOLUTION = (480, 360)
MAX_NAME_LENGTH = 16


def default_name():
    try:
        name = getpass.getuser()
    except Exception:
        name = ""
    return (name[:1].upper() + name[1:])[:MAX_NAME_LENGTH] or "Player"


@dataclass
class Settings:
    resolution: tuple = DEFAULT_RESOLUTION
    fullscreen: bool = False
    player_name: str = field(default_factory=default_name)

    default_name = staticmethod(default_name)

    @classmethod
    def load(cls):
        try:
            with open(SETTINGS_PATH, encoding="utf-8") as f:
                data = json.load(f)
            w, h = (int(v) for v in data["resolution"])
            return cls(
                resolution=(max(w, MIN_RESOLUTION[0]), max(h, MIN_RESOLUTION[1])),
                fullscreen=bool(data.get("fullscreen", False)),
                player_name=str(data.get("player_name") or default_name())[:MAX_NAME_LENGTH],
            )
        except (OSError, ValueError, KeyError, TypeError):
            return cls()

    def save(self):
        try:
            with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump({
                    "resolution": list(self.resolution),
                    "fullscreen": self.fullscreen,
                    "player_name": self.player_name,
                }, f, indent=2)
        except OSError:
            pass


def windowed_resolutions(desktop_size, current):
    """Presets that fit on the desktop (leaving room for the title bar), plus the current size."""
    dw, dh = desktop_size
    options = [r for r in RESOLUTION_PRESETS if r[0] <= dw and r[1] < dh]
    if tuple(current) not in options:
        options.append(tuple(current))
    return sorted(options)
