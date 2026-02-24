from __future__ import annotations

from pathlib import Path


TITLE = "Gravity Rotate"

BASE_W = 960
BASE_H = 540
FPS = 60
DT_CLAMP_MAX = 1.0 / 30.0

PLAYER_SIZE = 24
GRAVITY_ACC = 1200.0
MAX_SPEED = 520.0
ROTATE_COOLDOWN_SEC = 0.06

PORTAL_COOLDOWN_SEC = 0.20
TELEPORT_FLASH_SEC = 0.08

CLICK_PARTICLE_MIN = 10
CLICK_PARTICLE_MAX = 20

MAP_DIR = Path("map")
SAVE_FILE = Path("save.json")

DEFAULT_SETTINGS = {
    "master_volume": 70,
    "fullscreen": False,
    "screen_scale": 1,
    "screen_shake": True,
}

