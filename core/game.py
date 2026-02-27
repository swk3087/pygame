from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pygame

from core.assets import AssetManager
from core.config import BASE_H, BASE_W, DT_CLAMP_MAX, FPS, MAP_DIR, SAVE_FILE, TITLE
from core.save import (
    load_save_data,
    sanitize_settings,
    update_best_record,
    write_save_data,
)
from core.scene_manager import SceneManager
from gameplay.tilemap import MapValidationError, TileMap


@dataclass(slots=True)
class LevelEntry:
    index: int
    path: Path
    level_id: str
    name: str
    difficulty: str
    valid: bool
    issue: str | None
    spike_count: int
    portal_group_count: int
    size_text: str


class Game:
    def __init__(self) -> None:
        pygame.init()
        pygame.font.init()

        self.save_data = load_save_data(SAVE_FILE)
        self.save_data["settings"] = sanitize_settings(self.save_data.get("settings"))
        self.settings = self.save_data["settings"]

        self.assets = AssetManager(Path("assets"))
        self.assets.set_ui_scale(int(self.settings.get("ui_scale_percent", 100)))
        self.assets.set_master_volume(self.settings["master_volume"])
        print(f"[assets] ui font source: {self.assets.font_source()}")
        self.scene_manager = SceneManager()
        self.clock = pygame.time.Clock()
        self.running = True

        self.screen = pygame.Surface((BASE_W, BASE_H))
        self.output_rect = pygame.Rect(0, 0, BASE_W, BASE_H)
        self.present_size = (BASE_W, BASE_H)
        self.min_window_size = (480, 270)
        self._apply_display_mode()
        self.base_surface = pygame.Surface((BASE_W, BASE_H))

        self.level_entries = self._discover_levels()
        self._ensure_unlock_bounds()
        self.save()

    def _discover_levels(self) -> list[LevelEntry]:
        entries: list[LevelEntry] = []
        map_dir = MAP_DIR
        map_dir.mkdir(exist_ok=True, parents=True)
        paths = sorted(map_dir.glob("*.json"), key=lambda p: p.name.lower())
        for index, path in enumerate(paths):
            level_id, level_name, difficulty = TileMap.read_level_meta(path)
            valid = True
            issue: str | None = None
            spike_count = 0
            portal_group_count = 0
            size_text = "?"
            try:
                tilemap = TileMap.from_json(path)
                spike_count = len(tilemap.spike_tiles)
                portal_group_count = len(tilemap.portal_groups)
                size_text = f"{tilemap.width}x{tilemap.height}"
            except MapValidationError as exc:
                valid = False
                issue = str(exc)
            entries.append(
                LevelEntry(
                    index=index,
                    path=path,
                    level_id=level_id,
                    name=level_name,
                    difficulty=difficulty,
                    valid=valid,
                    issue=issue,
                    spike_count=spike_count,
                    portal_group_count=portal_group_count,
                    size_text=size_text,
                )
            )
        return entries

    def _ensure_unlock_bounds(self) -> None:
        level_count = len(self.level_entries)
        unlocked = int(self.save_data.get("unlocked_level_count", 1))
        if level_count <= 0:
            self.save_data["unlocked_level_count"] = 0
        else:
            self.save_data["unlocked_level_count"] = max(1, min(level_count, unlocked))

    def _apply_display_mode(self, window_size: tuple[int, int] | None = None) -> None:
        fullscreen = bool(self.settings.get("fullscreen", False))
        if fullscreen:
            flags = pygame.FULLSCREEN
            self.screen = pygame.display.set_mode((0, 0), flags)
        else:
            if window_size is None:
                scale = int(self.settings.get("screen_scale", 1))
                win_w = BASE_W * max(1, min(3, scale))
                win_h = BASE_H * max(1, min(3, scale))
            else:
                win_w = max(self.min_window_size[0], int(window_size[0]))
                win_h = max(self.min_window_size[1], int(window_size[1]))
            self.screen = pygame.display.set_mode((win_w, win_h), pygame.RESIZABLE)
        self.present_size = self.screen.get_size()
        self.output_rect = self._calc_output_rect(self.present_size[0], self.present_size[1])
        pygame.display.set_caption(TITLE)

    @staticmethod
    def _calc_output_rect(screen_w: int, screen_h: int) -> pygame.Rect:
        scale = min(screen_w / BASE_W, screen_h / BASE_H)
        draw_w = max(1, int(BASE_W * scale))
        draw_h = max(1, int(BASE_H * scale))
        draw_x = (screen_w - draw_w) // 2
        draw_y = (screen_h - draw_h) // 2
        return pygame.Rect(draw_x, draw_y, draw_w, draw_h)

    def window_to_base(self, pos: tuple[int, int]) -> tuple[int, int] | None:
        if not self.output_rect.collidepoint(pos):
            return None
        rel_x = (pos[0] - self.output_rect.left) / self.output_rect.width
        rel_y = (pos[1] - self.output_rect.top) / self.output_rect.height
        base_x = int(rel_x * BASE_W)
        base_y = int(rel_y * BASE_H)
        return base_x, base_y

    def finger_to_base(self, x: float, y: float) -> tuple[int, int] | None:
        win_x = int(x * self.present_size[0])
        win_y = int(y * self.present_size[1])
        return self.window_to_base((win_x, win_y))

    def set_setting(self, key: str, value: Any) -> None:
        self.settings[key] = value
        self.settings = sanitize_settings(self.settings)
        self.save_data["settings"] = self.settings
        if key == "master_volume":
            self.assets.set_master_volume(int(self.settings["master_volume"]))
        if key == "ui_scale_percent":
            self.assets.set_ui_scale(int(self.settings["ui_scale_percent"]))
        if key in {"fullscreen", "screen_scale"}:
            self._apply_display_mode()
        scene = self.scene_manager.current_scene()
        if scene is not None:
            on_settings_changed = getattr(scene, "on_settings_changed", None)
            if callable(on_settings_changed):
                on_settings_changed()
        self.save()

    def save(self) -> None:
        write_save_data(SAVE_FILE, self.save_data)

    def request_quit(self) -> None:
        self.running = False

    def start_level(self, level_index: int) -> None:
        if level_index < 0 or level_index >= len(self.level_entries):
            return
        entry = self.level_entries[level_index]
        if not entry.valid:
            print(f"[level] start blocked (invalid map): {entry.path.name} - {entry.issue}")
            return
        from scenes.game_scene import GameScene

        self.scene_manager.replace(GameScene(self, level_index))

    def start_first_playable_level(self) -> None:
        unlocked = int(self.save_data.get("unlocked_level_count", 1))
        for entry in self.level_entries:
            if entry.index >= unlocked:
                continue
            if entry.valid:
                self.start_level(entry.index)
                return
        if self.level_entries:
            self.open_level_select()

    def next_playable_level_index(self, current_index: int) -> int | None:
        unlocked = int(self.save_data.get("unlocked_level_count", 1))
        for entry in self.level_entries:
            if entry.index <= current_index:
                continue
            if entry.index >= unlocked:
                continue
            if entry.valid:
                return entry.index
        return None

    def open_main_menu(self) -> None:
        from scenes.main_menu import MainMenuScene

        self.scene_manager.replace(MainMenuScene(self))

    def open_level_select(self) -> None:
        from scenes.level_select import LevelSelectScene

        self.scene_manager.replace(LevelSelectScene(self))

    def open_settings(self) -> None:
        from scenes.settings import SettingsScene

        self.scene_manager.push(SettingsScene(self))

    def open_results(self, result_data: dict[str, Any]) -> None:
        from scenes.results import ResultsScene

        self.scene_manager.replace(ResultsScene(self, result_data))

    def complete_level(self, result_data: dict[str, Any]) -> None:
        level_index = int(result_data.get("level_index", 0))
        level_id = str(result_data.get("level_id", "unknown"))
        clicks = int(result_data.get("clicks", 0))
        time_sec = float(result_data.get("time_sec", 0.0))

        unlocked = int(self.save_data.get("unlocked_level_count", 1))
        unlock_target = level_index + 2
        if self.level_entries:
            self.save_data["unlocked_level_count"] = min(
                len(self.level_entries),
                max(unlocked, unlock_target),
            )
        update_best_record(self.save_data, level_id, clicks, time_sec)
        self.save()
        next_index = self.next_playable_level_index(level_index)
        result_data["next_level_index"] = next_index
        self.open_results(result_data)

    def run(self) -> None:
        from scenes.main_menu import MainMenuScene

        self.scene_manager.push(MainMenuScene(self))

        while self.running:
            raw_dt = self.clock.tick(FPS) / 1000.0
            dt = min(raw_dt, DT_CLAMP_MAX)

            current_scene = self.scene_manager.current_scene()
            if current_scene is None:
                break

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    break
                if event.type == pygame.VIDEORESIZE and not self.settings.get("fullscreen", False):
                    self._apply_display_mode((event.w, event.h))
                    continue
                if (
                    event.type == pygame.WINDOWSIZECHANGED
                    and not self.settings.get("fullscreen", False)
                ):
                    self.present_size = self.screen.get_size()
                    self.output_rect = self._calc_output_rect(
                        self.present_size[0], self.present_size[1]
                    )
                    continue
                scene = self.scene_manager.current_scene()
                if scene is None:
                    self.running = False
                    break
                scene.handle_event(event)

            if not self.running:
                break

            scene = self.scene_manager.current_scene()
            if scene is None:
                break
            scene.update(dt)
            scene = self.scene_manager.current_scene()
            if scene is None:
                break

            self.base_surface.fill((9, 11, 19))
            scene.render(self.base_surface)

            self.screen.fill((0, 0, 0))
            scaled = pygame.transform.smoothscale(
                self.base_surface, (self.output_rect.width, self.output_rect.height)
            )
            self.screen.blit(scaled, self.output_rect.topleft)
            pygame.display.flip()

        pygame.quit()
