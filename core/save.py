from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from core.config import DEFAULT_SETTINGS
from core.utils import clamp, safe_int


SAVE_SCHEMA_VERSION = 1


def default_save_data() -> dict[str, Any]:
    return {
        "schema_version": SAVE_SCHEMA_VERSION,
        "unlocked_level_count": 1,
        "best_records": {},
        "settings": deepcopy(DEFAULT_SETTINGS),
    }


def sanitize_settings(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raw = {}
    settings = deepcopy(DEFAULT_SETTINGS)
    settings["master_volume"] = safe_int(raw.get("master_volume"), settings["master_volume"])
    settings["master_volume"] = int(clamp(settings["master_volume"], 0, 100))
    settings["fullscreen"] = bool(raw.get("fullscreen", settings["fullscreen"]))
    scale = safe_int(raw.get("screen_scale"), settings["screen_scale"])
    settings["screen_scale"] = int(clamp(scale, 1, 3))
    settings["screen_shake"] = bool(raw.get("screen_shake", settings["screen_shake"]))
    return settings


def sanitize_save_data(raw: Any) -> dict[str, Any]:
    data = default_save_data()
    if not isinstance(raw, dict):
        return data

    unlocked = safe_int(raw.get("unlocked_level_count"), 1)
    data["unlocked_level_count"] = max(1, unlocked)

    best_records = raw.get("best_records", {})
    if isinstance(best_records, dict):
        safe_records: dict[str, dict[str, float]] = {}
        for level_id, record in best_records.items():
            if not isinstance(level_id, str) or not isinstance(record, dict):
                continue
            clicks = safe_int(record.get("clicks"), 999999)
            time_sec = float(record.get("time_sec", 999999.0))
            if clicks < 0:
                clicks = 0
            if time_sec < 0.0:
                time_sec = 0.0
            safe_records[level_id] = {"clicks": clicks, "time_sec": time_sec}
        data["best_records"] = safe_records

    data["settings"] = sanitize_settings(raw.get("settings", {}))
    return data


def load_save_data(path: Path) -> dict[str, Any]:
    if not path.exists():
        return default_save_data()
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[save] load failed: {exc}")
        return default_save_data()
    return sanitize_save_data(loaded)


def write_save_data(path: Path, data: dict[str, Any]) -> None:
    try:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:
        print(f"[save] write failed: {exc}")


def update_best_record(
    data: dict[str, Any],
    level_id: str,
    clicks: int,
    time_sec: float,
) -> None:
    best_records = data.setdefault("best_records", {})
    previous = best_records.get(level_id)
    if not isinstance(previous, dict):
        best_records[level_id] = {"clicks": clicks, "time_sec": time_sec}
        return

    prev_clicks = safe_int(previous.get("clicks"), 999999)
    prev_time = float(previous.get("time_sec", 999999.0))
    better = clicks < prev_clicks or (clicks == prev_clicks and time_sec < prev_time)
    if better:
        best_records[level_id] = {"clicks": clicks, "time_sec": time_sec}

