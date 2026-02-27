from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pygame


EMPTY = "EMPTY"
WALL = "WALL"
SPAWN = "SPAWN"
GOAL = "GOAL"
SPIKE = "SPIKE"
PORTAL = "PORTAL"

SOLID_TILES = {WALL}
DIFFICULTY_VALUES = {"tutorial", "mid", "hard"}


class MapValidationError(Exception):
    pass


@dataclass(slots=True)
class PortalNode:
    portal_id: int
    tx: int
    ty: int
    index: int

    def rect(self, tile_size: int) -> pygame.Rect:
        return pygame.Rect(self.tx * tile_size, self.ty * tile_size, tile_size, tile_size)

    def center(self, tile_size: int) -> tuple[int, int]:
        r = self.rect(tile_size)
        return r.centerx, r.centery


@dataclass(slots=True)
class TutorialText:
    at: tuple[int, int]
    message: str


class TileMap:
    def __init__(
        self,
        map_path: Path,
        level_id: str,
        level_name: str,
        tile_size: int,
        width: int,
        height: int,
        tile_types: list[list[str]],
        portal_ids: list[list[int | None]],
        grid: list[str],
        spawn_px: tuple[float, float],
        goal_tiles: list[pygame.Rect],
        spike_tiles: list[pygame.Rect],
        portal_groups: dict[int, list[PortalNode]],
        tutorial_entries: list[TutorialText],
    ) -> None:
        self.map_path = map_path
        self.level_id = level_id
        self.level_name = level_name
        self.tile_size = tile_size
        self.width = width
        self.height = height
        self.tile_types = tile_types
        self.portal_ids = portal_ids
        self.grid = grid
        self.spawn_px = spawn_px
        self.goal_tiles = goal_tiles
        self.spike_tiles = spike_tiles
        self.portal_groups = portal_groups
        self.tutorial_entries = tutorial_entries

    @property
    def pixel_size(self) -> tuple[int, int]:
        return self.width * self.tile_size, self.height * self.tile_size

    @classmethod
    def from_json(cls, path: Path) -> TileMap:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise MapValidationError(f"JSON 로드 실패: {exc}") from exc

        if not isinstance(data, dict):
            raise MapValidationError("JSON 루트는 객체여야 합니다.")

        meta = data.get("meta")
        if not isinstance(meta, dict):
            raise MapValidationError("meta 객체가 필요합니다.")
        level_id = str(meta.get("id", path.stem))
        level_name = str(meta.get("name", path.stem))

        tile_size = int(data.get("tile_size", 32))
        width = int(data.get("width", 0))
        height = int(data.get("height", 0))
        legend = data.get("legend")
        grid = data.get("grid")
        tutorial = data.get("tutorial", [])

        if tile_size <= 0:
            raise MapValidationError("tile_size는 1 이상이어야 합니다.")
        if width <= 0 or height <= 0:
            raise MapValidationError("width/height는 1 이상이어야 합니다.")
        if not isinstance(legend, dict):
            raise MapValidationError("legend 객체가 필요합니다.")
        if not isinstance(grid, list) or not all(isinstance(row, str) for row in grid):
            raise MapValidationError("grid는 문자열 배열이어야 합니다.")

        if len(grid) != height:
            raise MapValidationError(
                f"height({height})와 grid 줄 수({len(grid)})가 일치하지 않습니다."
            )
        for i, row in enumerate(grid):
            if len(row) != width:
                raise MapValidationError(
                    f"width({width})와 grid[{i}] 길이({len(row)})가 일치하지 않습니다."
                )

        tile_types: list[list[str]] = [[EMPTY for _ in range(width)] for _ in range(height)]
        portal_ids: list[list[int | None]] = [[None for _ in range(width)] for _ in range(height)]
        spawn_tiles: list[tuple[int, int]] = []
        goal_tiles: list[pygame.Rect] = []
        spike_tiles: list[pygame.Rect] = []
        portal_groups: dict[int, list[PortalNode]] = {}

        portal_index = 0
        for ty, row in enumerate(grid):
            for tx, ch in enumerate(row):
                mapped = legend.get(ch)
                if not isinstance(mapped, str):
                    raise MapValidationError(f"legend에 없는 문자: '{ch}' at ({tx},{ty})")
                if mapped.startswith("PORTAL:"):
                    portal_id = cls._parse_portal_id(mapped, tx, ty)
                    tile_types[ty][tx] = PORTAL
                    portal_ids[ty][tx] = portal_id
                    portal_groups.setdefault(portal_id, []).append(
                        PortalNode(portal_id=portal_id, tx=tx, ty=ty, index=portal_index)
                    )
                    portal_index += 1
                    continue

                tile_type = mapped.strip().upper()
                if tile_type not in {EMPTY, WALL, SPAWN, GOAL, SPIKE}:
                    raise MapValidationError(f"알 수 없는 타일 타입: {mapped}")
                tile_types[ty][tx] = tile_type
                tile_rect = pygame.Rect(tx * tile_size, ty * tile_size, tile_size, tile_size)
                if tile_type == SPAWN:
                    spawn_tiles.append((tx, ty))
                elif tile_type == GOAL:
                    goal_tiles.append(tile_rect)
                elif tile_type == SPIKE:
                    spike_tiles.append(tile_rect)

        if not spawn_tiles:
            raise MapValidationError("SPAWN(S) 타일이 없습니다.")
        if len(spawn_tiles) > 1:
            print(f"[map] warning: SPAWN이 {len(spawn_tiles)}개입니다. 첫 번째만 사용합니다.")
        spawn_tx, spawn_ty = spawn_tiles[0]
        spawn_px = (
            spawn_tx * tile_size + tile_size / 2.0,
            spawn_ty * tile_size + tile_size / 2.0,
        )
        if not goal_tiles:
            print("[map] warning: GOAL이 없습니다.")

        tutorial_entries: list[TutorialText] = []
        if isinstance(tutorial, list):
            for entry in tutorial:
                if not isinstance(entry, dict):
                    continue
                if entry.get("type") != "text":
                    continue
                at = entry.get("at")
                msg = entry.get("message")
                if (
                    isinstance(at, list)
                    and len(at) == 2
                    and isinstance(at[0], int)
                    and isinstance(at[1], int)
                    and isinstance(msg, str)
                ):
                    tutorial_entries.append(TutorialText((at[0], at[1]), msg))

        return cls(
            map_path=path,
            level_id=level_id,
            level_name=level_name,
            tile_size=tile_size,
            width=width,
            height=height,
            tile_types=tile_types,
            portal_ids=portal_ids,
            grid=grid,
            spawn_px=spawn_px,
            goal_tiles=goal_tiles,
            spike_tiles=spike_tiles,
            portal_groups=portal_groups,
            tutorial_entries=tutorial_entries,
        )

    @staticmethod
    def _parse_portal_id(portal_text: str, tx: int, ty: int) -> int:
        _, _, portal_id_text = portal_text.partition(":")
        try:
            portal_id = int(portal_id_text)
        except ValueError as exc:
            raise MapValidationError(f"잘못된 포탈 id: {portal_text} at ({tx},{ty})") from exc
        return portal_id

    @classmethod
    def read_level_meta(cls, path: Path) -> tuple[str, str, str]:
        default_name = path.stem
        default_difficulty = cls.infer_difficulty(path.stem, default_name)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return path.stem, f"{path.stem} (오류)", default_difficulty
        if not isinstance(data, dict):
            return path.stem, f"{path.stem} (오류)", default_difficulty
        meta = data.get("meta", {})
        if not isinstance(meta, dict):
            return path.stem, default_name, default_difficulty
        level_id = str(meta.get("id", path.stem))
        level_name = str(meta.get("name", default_name))
        requested_difficulty = str(meta.get("difficulty", "")).strip().lower()
        if requested_difficulty in DIFFICULTY_VALUES:
            difficulty = requested_difficulty
        else:
            difficulty = cls.infer_difficulty(path.stem, level_name)
        return level_id, level_name, difficulty

    @staticmethod
    def infer_difficulty(file_stem: str, level_name: str) -> str:
        lowered = f"{file_stem} {level_name}".lower()
        if "tutorial" in lowered or "튜토리얼" in lowered:
            return "tutorial"
        if "고난도" in lowered or "hard" in lowered:
            return "hard"
        if "중간" in lowered or "mid" in lowered:
            return "mid"
        return "mid"

    def tile_rect(self, tx: int, ty: int) -> pygame.Rect:
        return pygame.Rect(tx * self.tile_size, ty * self.tile_size, self.tile_size, self.tile_size)

    def tile_index_at(self, x: float, y: float) -> tuple[int, int]:
        return int(x // self.tile_size), int(y // self.tile_size)

    def tile_type_at(self, tx: int, ty: int) -> str:
        if tx < 0 or ty < 0 or tx >= self.width or ty >= self.height:
            return WALL
        return self.tile_types[ty][tx]

    def portal_id_at(self, tx: int, ty: int) -> int | None:
        if tx < 0 or ty < 0 or tx >= self.width or ty >= self.height:
            return None
        return self.portal_ids[ty][tx]

    def get_solid_rects_near(self, rect: pygame.Rect) -> list[pygame.Rect]:
        min_tx = int(rect.left // self.tile_size) - 1
        max_tx = int(rect.right // self.tile_size) + 1
        min_ty = int(rect.top // self.tile_size) - 1
        max_ty = int(rect.bottom // self.tile_size) + 1
        solid_rects: list[pygame.Rect] = []
        for ty in range(min_ty, max_ty + 1):
            for tx in range(min_tx, max_tx + 1):
                if self.tile_type_at(tx, ty) in SOLID_TILES:
                    solid_rects.append(self.tile_rect(tx, ty))
        return solid_rects

    def draw(self, surface: pygame.Surface, elapsed_sec: float, camera_offset: pygame.Vector2) -> None:
        offset_x = int(camera_offset.x)
        offset_y = int(camera_offset.y)
        wall_color = (70, 82, 110)
        wall_edge = (32, 40, 60)
        goal_color = (88, 176, 106)
        spike_color = (193, 83, 83)
        spawn_color = (100, 112, 138)
        portal_color = (102, 212, 214)

        for ty in range(self.height):
            for tx in range(self.width):
                tile_type = self.tile_types[ty][tx]
                rect = self.tile_rect(tx, ty).move(offset_x, offset_y)
                if tile_type == WALL:
                    pygame.draw.rect(surface, wall_color, rect)
                    pygame.draw.rect(surface, wall_edge, rect, width=1)
                elif tile_type == GOAL:
                    pygame.draw.rect(surface, goal_color, rect.inflate(-6, -6), border_radius=6)
                    pygame.draw.rect(surface, (20, 30, 22), rect.inflate(-6, -6), width=2, border_radius=6)
                elif tile_type == SPIKE:
                    p1 = (rect.left + 4, rect.bottom - 4)
                    p2 = (rect.centerx, rect.top + 4)
                    p3 = (rect.right - 4, rect.bottom - 4)
                    pygame.draw.polygon(surface, spike_color, [p1, p2, p3])
                elif tile_type == SPAWN:
                    pygame.draw.rect(surface, spawn_color, rect.inflate(-8, -8), border_radius=5)
                    pygame.draw.rect(
                        surface, (42, 50, 66), rect.inflate(-8, -8), width=1, border_radius=5
                    )

        for group in self.portal_groups.values():
            for node in group:
                rect = node.rect(self.tile_size).move(offset_x, offset_y)
                center = rect.center
                portal_fill = rect.inflate(-8, -8)
                pygame.draw.rect(surface, (34, 86, 110), portal_fill, border_radius=7)
                pygame.draw.rect(surface, (18, 38, 50), portal_fill, width=1, border_radius=7)
                ring_radius = int(self.tile_size * (0.2 + (elapsed_sec * 2.0 % 1.0) * 0.4))
                pygame.draw.circle(surface, portal_color, center, max(6, ring_radius), width=2)
                pygame.draw.circle(surface, (30, 85, 90), center, max(2, ring_radius - 5), width=1)
