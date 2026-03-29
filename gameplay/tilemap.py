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

Color = tuple[int, int, int]

FLOOR_BASE: Color = (34, 42, 58)
WALL_BASE: Color = (70, 82, 110)
WALL_INNER: Color = (84, 97, 129)
GOAL_BASE: Color = (88, 176, 106)
SPIKE_BASE: Color = (201, 93, 88)
SPAWN_BASE: Color = (104, 118, 144)
PORTAL_BASE: Color = (50, 114, 138)
PORTAL_GLOW: Color = (110, 224, 228)


def _clamp_channel(value: float) -> int:
    return max(0, min(255, int(round(value))))


def _shift_color(color: Color, delta: float) -> Color:
    return tuple(_clamp_channel(channel + delta) for channel in color)  # type: ignore[return-value]


def _mix_color(left: Color, right: Color, t: float) -> Color:
    safe_t = max(0.0, min(1.0, t))
    return tuple(
        _clamp_channel(left[i] + (right[i] - left[i]) * safe_t) for i in range(3)
    )  # type: ignore[return-value]


def _stable_seed(tx: int, ty: int, salt: int = 0) -> int:
    return ((tx + 11) * 92821) ^ ((ty + 17) * 68917) ^ ((salt + 29) * 131071)


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
        self._panel_margin = max(18, tile_size // 2)
        self._panel_surface: pygame.Surface | None = None
        self._static_surface: pygame.Surface | None = None

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

    def _tile_rect_local(self, tx: int, ty: int) -> pygame.Rect:
        return pygame.Rect(tx * self.tile_size, ty * self.tile_size, self.tile_size, self.tile_size)

    def _neighbor_walls(self, tx: int, ty: int) -> tuple[bool, bool, bool, bool]:
        return (
            self.tile_type_at(tx, ty - 1) == WALL,
            self.tile_type_at(tx + 1, ty) == WALL,
            self.tile_type_at(tx, ty + 1) == WALL,
            self.tile_type_at(tx - 1, ty) == WALL,
        )

    def _build_panel_surface(self) -> pygame.Surface:
        map_w, map_h = self.pixel_size
        margin = self._panel_margin
        surface = pygame.Surface((map_w + margin * 2, map_h + margin * 2), pygame.SRCALPHA)
        panel = pygame.Rect(margin, margin, map_w, map_h)

        for i in range(10, 0, -1):
            spread = i * 4
            alpha = 10 + i * 4
            pygame.draw.rect(
                surface,
                (0, 0, 0, alpha),
                panel.inflate(spread * 2, spread * 2),
                border_radius=22 + spread // 4,
            )

        outer = panel.inflate(18, 18)
        inner = panel.inflate(8, 8)
        pygame.draw.rect(surface, (18, 22, 33, 230), outer, border_radius=26)
        pygame.draw.rect(surface, (28, 35, 48, 240), inner, border_radius=20)
        pygame.draw.rect(surface, (86, 102, 132, 110), inner, width=2, border_radius=20)

        bracket_color = (112, 132, 170, 120)
        bracket = 18
        corners = [
            (inner.left + 8, inner.top + 8, 1, 1),
            (inner.right - 8, inner.top + 8, -1, 1),
            (inner.left + 8, inner.bottom - 8, 1, -1),
            (inner.right - 8, inner.bottom - 8, -1, -1),
        ]
        for cx, cy, sx, sy in corners:
            pygame.draw.line(surface, bracket_color, (cx, cy), (cx + bracket * sx, cy), width=3)
            pygame.draw.line(surface, bracket_color, (cx, cy), (cx, cy + bracket * sy), width=3)

        return surface

    def _build_static_surface(self) -> pygame.Surface:
        map_w, map_h = self.pixel_size
        surface = pygame.Surface((map_w, map_h), pygame.SRCALPHA)
        for ty in range(self.height):
            for tx in range(self.width):
                tile_type = self.tile_types[ty][tx]
                rect = self._tile_rect_local(tx, ty)
                if tile_type == WALL:
                    self._draw_wall_tile(surface, rect, tx, ty)
                elif tile_type == GOAL:
                    self._draw_goal_tile(surface, rect, tx, ty)
                elif tile_type == SPIKE:
                    self._draw_spike_tile(surface, rect, tx, ty)
                elif tile_type == SPAWN:
                    self._draw_spawn_tile(surface, rect, tx, ty)
                elif tile_type == PORTAL:
                    self._draw_portal_base(surface, rect, tx, ty)
                else:
                    self._draw_floor_tile(surface, rect, tx, ty)
        return surface

    def _ensure_render_cache(self) -> None:
        if self._panel_surface is None:
            self._panel_surface = self._build_panel_surface()
        if self._static_surface is None:
            self._static_surface = self._build_static_surface()

    def _draw_floor_tile(self, surface: pygame.Surface, rect: pygame.Rect, tx: int, ty: int) -> None:
        seed = _stable_seed(tx, ty, 3)
        base = _shift_color(FLOOR_BASE, (seed % 7) - 3)
        panel = rect.inflate(-2, -2)
        core = panel.inflate(-6, -6)
        pygame.draw.rect(surface, _shift_color(base, -8), rect)
        pygame.draw.rect(surface, base, panel, border_radius=5)
        pygame.draw.rect(surface, _shift_color(base, -6), core, border_radius=4)

        line_color = _shift_color(base, 16)
        if seed & 1:
            split_x = core.left + core.width // 2
            pygame.draw.line(surface, _shift_color(base, -18), (split_x, core.top + 3), (split_x, core.bottom - 3))
        else:
            split_y = core.top + core.height // 2
            pygame.draw.line(surface, _shift_color(base, -18), (core.left + 3, split_y), (core.right - 3, split_y))

        if seed % 5 == 0:
            plate = pygame.Rect(core.left + 4, core.top + 4, core.width - 8, 6)
            pygame.draw.rect(surface, _shift_color(line_color, -4), plate, border_radius=3)
        elif seed % 5 == 1:
            plate = pygame.Rect(core.left + 5, core.bottom - 10, core.width - 10, 5)
            pygame.draw.rect(surface, _shift_color(line_color, -6), plate, border_radius=3)

        bolt_color = _shift_color(base, 32)
        for bx, by in ((core.left + 5, core.top + 5), (core.right - 5, core.bottom - 5)):
            pygame.draw.circle(surface, bolt_color, (bx, by), 2)
            pygame.draw.circle(surface, _shift_color(bolt_color, -34), (bx, by), 2, width=1)

        top_wall, right_wall, bottom_wall, left_wall = self._neighbor_walls(tx, ty)
        shadow = pygame.Surface(rect.size, pygame.SRCALPHA)
        if top_wall:
            pygame.draw.rect(shadow, (0, 0, 0, 55), pygame.Rect(0, 0, rect.width, max(4, rect.height // 6)))
        if left_wall:
            pygame.draw.rect(shadow, (0, 0, 0, 45), pygame.Rect(0, 0, max(4, rect.width // 6), rect.height))
        if right_wall:
            pygame.draw.rect(
                shadow,
                (120, 140, 170, 18),
                pygame.Rect(rect.width - max(3, rect.width // 7), 0, max(3, rect.width // 7), rect.height),
            )
        if bottom_wall:
            pygame.draw.rect(
                shadow,
                (120, 140, 170, 14),
                pygame.Rect(0, rect.height - max(3, rect.height // 7), rect.width, max(3, rect.height // 7)),
            )
        surface.blit(shadow, rect.topleft)

    def _draw_wall_tile(self, surface: pygame.Surface, rect: pygame.Rect, tx: int, ty: int) -> None:
        seed = _stable_seed(tx, ty, 7)
        top_wall, right_wall, bottom_wall, left_wall = self._neighbor_walls(tx, ty)
        pygame.draw.rect(surface, _shift_color(WALL_BASE, -12), rect)
        body = rect.inflate(-2, -2)
        pygame.draw.rect(surface, _shift_color(WALL_BASE, (seed % 5) - 2), body)
        inset = body.inflate(-5, -5)
        pygame.draw.rect(surface, _shift_color(WALL_INNER, (seed % 7) - 3), inset, border_radius=4)

        if not top_wall:
            pygame.draw.rect(surface, _shift_color(WALL_INNER, 36), pygame.Rect(rect.left, rect.top, rect.width, 5))
        if not left_wall:
            pygame.draw.rect(surface, _shift_color(WALL_INNER, 22), pygame.Rect(rect.left, rect.top, 4, rect.height))
        if not right_wall:
            pygame.draw.rect(surface, _shift_color(WALL_BASE, -28), pygame.Rect(rect.right - 5, rect.top, 5, rect.height))
        if not bottom_wall:
            pygame.draw.rect(surface, _shift_color(WALL_BASE, -32), pygame.Rect(rect.left, rect.bottom - 5, rect.width, 5))

        detail_color = _shift_color(WALL_INNER, 18)
        if seed % 3 == 0:
            vent = pygame.Rect(inset.left + 5, inset.centery - 3, inset.width - 10, 6)
            pygame.draw.rect(surface, _shift_color(WALL_BASE, -20), vent, border_radius=3)
            for stripe in range(vent.left + 4, vent.right - 1, 6):
                pygame.draw.line(surface, detail_color, (stripe, vent.top + 1), (stripe, vent.bottom - 2))
        elif seed % 3 == 1:
            panel = pygame.Rect(inset.left + 6, inset.top + 6, inset.width - 12, inset.height - 12)
            pygame.draw.rect(surface, _shift_color(WALL_BASE, -10), panel, width=2, border_radius=3)
            for bx, by in ((panel.left + 4, panel.top + 4), (panel.right - 4, panel.bottom - 4)):
                pygame.draw.circle(surface, detail_color, (bx, by), 2)

    def _draw_spawn_tile(self, surface: pygame.Surface, rect: pygame.Rect, tx: int, ty: int) -> None:
        self._draw_floor_tile(surface, rect, tx, ty)
        pad = rect.inflate(-8, -8)
        inner = pad.inflate(-8, -8)
        pygame.draw.rect(surface, _shift_color(SPAWN_BASE, -12), pad, border_radius=7)
        pygame.draw.rect(surface, _shift_color(SPAWN_BASE, 18), pad, width=2, border_radius=7)
        pygame.draw.rect(surface, _shift_color(SPAWN_BASE, 8), inner, border_radius=5)
        arrow_color = _shift_color(SPAWN_BASE, 42)
        center_x, center_y = rect.center
        arrows = [
            [(center_x, pad.top + 3), (center_x - 4, pad.top + 10), (center_x + 4, pad.top + 10)],
            [(center_x, pad.bottom - 3), (center_x - 4, pad.bottom - 10), (center_x + 4, pad.bottom - 10)],
            [(pad.left + 3, center_y), (pad.left + 10, center_y - 4), (pad.left + 10, center_y + 4)],
            [(pad.right - 3, center_y), (pad.right - 10, center_y - 4), (pad.right - 10, center_y + 4)],
        ]
        for arrow in arrows:
            pygame.draw.polygon(surface, arrow_color, arrow)

    def _draw_goal_tile(self, surface: pygame.Surface, rect: pygame.Rect, tx: int, ty: int) -> None:
        self._draw_floor_tile(surface, rect, tx, ty)
        pad = rect.inflate(-7, -7)
        inner = pad.inflate(-10, -10)
        pygame.draw.rect(surface, _shift_color(GOAL_BASE, -18), pad, border_radius=8)
        pygame.draw.rect(surface, _shift_color(GOAL_BASE, 26), pad, width=2, border_radius=8)
        pygame.draw.rect(surface, _shift_color(GOAL_BASE, 12), inner, border_radius=6)
        for offset in (0, 7):
            band = pygame.Rect(inner.left + 4, inner.top + 5 + offset, inner.width - 8, 3)
            pygame.draw.rect(surface, _mix_color(_shift_color(GOAL_BASE, 44), (235, 255, 246), 0.45), band, border_radius=2)
        glow = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.ellipse(glow, (150, 255, 180, 34), pygame.Rect(2, 4, rect.width - 4, rect.height - 8))
        surface.blit(glow, rect.topleft)

    def _draw_spike_tile(self, surface: pygame.Surface, rect: pygame.Rect, tx: int, ty: int) -> None:
        self._draw_floor_tile(surface, rect, tx, ty)
        glow = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.ellipse(glow, (255, 96, 96, 18), pygame.Rect(1, 9, rect.width - 2, rect.height - 10))
        surface.blit(glow, rect.topleft)

        plate = pygame.Rect(rect.left + 3, rect.bottom - 9, rect.width - 6, 6)
        pygame.draw.rect(surface, _shift_color(SPIKE_BASE, -26), plate, border_radius=3)
        for stripe_x in range(plate.left + 2, plate.right - 1, 8):
            points = [(stripe_x, plate.bottom), (stripe_x + 4, plate.top), (stripe_x + 8, plate.top), (stripe_x + 4, plate.bottom)]
            pygame.draw.polygon(surface, _shift_color(SPIKE_BASE, 12), points)

        spike_w = max(6, rect.width // 4)
        gap = max(1, (rect.width - spike_w * 3) // 4)
        for index in range(3):
            left = rect.left + gap + index * (spike_w + gap)
            points = [
                (left, plate.top + 1),
                (left + spike_w // 2, rect.top + 5),
                (left + spike_w, plate.top + 1),
            ]
            pygame.draw.polygon(surface, _shift_color(SPIKE_BASE, -4), points)
            pygame.draw.polygon(surface, _shift_color(SPIKE_BASE, 32), points, width=1)
            pygame.draw.line(
                surface,
                _mix_color((255, 240, 240), _shift_color(SPIKE_BASE, 36), 0.5),
                (left + spike_w // 2, rect.top + 7),
                (left + spike_w - 2, plate.top - 1),
            )

    def _draw_portal_base(self, surface: pygame.Surface, rect: pygame.Rect, tx: int, ty: int) -> None:
        self._draw_floor_tile(surface, rect, tx, ty)
        housing = rect.inflate(-5, -4)
        core = housing.inflate(-8, -6)
        pygame.draw.rect(surface, _shift_color(PORTAL_BASE, -24), housing, border_radius=8)
        pygame.draw.rect(surface, _shift_color(PORTAL_BASE, 16), housing, width=2, border_radius=8)
        pygame.draw.rect(surface, _shift_color(PORTAL_BASE, -8), core, border_radius=6)
        pylons = [
            pygame.Rect(housing.left + 3, housing.top + 5, 4, housing.height - 10),
            pygame.Rect(housing.right - 7, housing.top + 5, 4, housing.height - 10),
        ]
        for pylon in pylons:
            pygame.draw.rect(surface, _shift_color(PORTAL_BASE, 28), pylon, border_radius=2)

    def _draw_portal_overlay(
        self,
        surface: pygame.Surface,
        center: tuple[int, int],
        elapsed_sec: float,
        seed_index: int,
    ) -> None:
        phase = (elapsed_sec * 1.75 + seed_index * 0.19) % 1.0
        ring_radius = int(self.tile_size * (0.22 + phase * 0.22))
        halo_radius = int(self.tile_size * (0.42 + phase * 0.08))
        halo = pygame.Surface((halo_radius * 2 + 12, halo_radius * 2 + 12), pygame.SRCALPHA)
        halo_rect = halo.get_rect(center=center)
        pygame.draw.circle(halo, (*PORTAL_GLOW, 28), halo.get_rect().center, halo_radius)
        pygame.draw.circle(halo, (*PORTAL_GLOW, 52), halo.get_rect().center, max(6, halo_radius - 4), width=4)
        surface.blit(halo, halo_rect.topleft)

        pygame.draw.circle(surface, _mix_color(PORTAL_GLOW, (255, 255, 255), 0.2), center, max(7, ring_radius), width=2)
        pygame.draw.circle(surface, _shift_color(PORTAL_BASE, 26), center, max(4, ring_radius - 6), width=2)

    def draw(self, surface: pygame.Surface, elapsed_sec: float, camera_offset: pygame.Vector2) -> None:
        self._ensure_render_cache()
        offset_x = int(camera_offset.x)
        offset_y = int(camera_offset.y)
        if self._panel_surface is not None:
            surface.blit(self._panel_surface, (offset_x - self._panel_margin, offset_y - self._panel_margin))
        if self._static_surface is not None:
            surface.blit(self._static_surface, (offset_x, offset_y))
        for group in self.portal_groups.values():
            for node in group:
                center = node.rect(self.tile_size).move(offset_x, offset_y).center
                self._draw_portal_overlay(surface, center, elapsed_sec, node.index)
