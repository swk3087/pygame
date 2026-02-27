from __future__ import annotations

import pygame

from core.config import GRAVITY_ACC, MAX_SPEED
from core.utils import clamp_vec_magnitude, rotate_vec_ccw, rotate_vec_cw
from gameplay.tilemap import SPIKE, WALL, TileMap


class Player:
    def __init__(self, spawn_center: tuple[float, float], size: int) -> None:
        self.size = size
        self.pos = pygame.Vector2(0.0, 0.0)
        self.vel = pygame.Vector2(0.0, 0.0)
        self.respawn(spawn_center)

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.pos.x), int(self.pos.y), self.size, self.size)

    @property
    def center(self) -> tuple[float, float]:
        return self.pos.x + self.size / 2.0, self.pos.y + self.size / 2.0

    def set_center(self, center: tuple[float, float]) -> None:
        self.pos.x = center[0] - self.size / 2.0
        self.pos.y = center[1] - self.size / 2.0

    def respawn(self, spawn_center: tuple[float, float]) -> None:
        self.set_center(spawn_center)
        self.vel.update(0.0, 0.0)

    def rotate_velocity_ccw(self) -> None:
        self.vel = rotate_vec_ccw(self.vel)

    def rotate_velocity_cw(self) -> None:
        self.vel = rotate_vec_cw(self.vel)

    def update(self, dt: float, gravity_vec: pygame.Vector2, tilemap: TileMap) -> None:
        self.vel += gravity_vec * GRAVITY_ACC * dt
        self.vel = clamp_vec_magnitude(self.vel, MAX_SPEED)

        self.pos.x += self.vel.x * dt
        self._resolve_collisions_x(tilemap)
        self.pos.y += self.vel.y * dt
        self._resolve_collisions_y(tilemap)

    def snap_to_nearest_tile(self, tilemap: TileMap) -> None:
        current = pygame.Vector2(self.center)
        tile_size = tilemap.tile_size
        current_tx, current_ty = tilemap.tile_index_at(current.x, current.y)

        best_safe_center: tuple[float, float] | None = None
        best_safe_dist2 = float("inf")
        best_any_center: tuple[float, float] | None = None
        best_any_dist2 = float("inf")

        # Keep snap correction local so rotation never jumps across the map.
        for ty in range(current_ty - 1, current_ty + 2):
            for tx in range(current_tx - 1, current_tx + 2):
                tile_type = tilemap.tile_type_at(tx, ty)
                if tile_type == WALL:
                    continue

                center = (
                    tx * tile_size + tile_size / 2.0,
                    ty * tile_size + tile_size / 2.0,
                )
                dx = center[0] - current.x
                dy = center[1] - current.y
                dist2 = dx * dx + dy * dy

                if dist2 < best_any_dist2:
                    best_any_dist2 = dist2
                    best_any_center = center

                if tile_type != SPIKE and dist2 < best_safe_dist2:
                    best_safe_dist2 = dist2
                    best_safe_center = center

        target = best_safe_center if best_safe_center is not None else best_any_center
        if target is not None:
            self.set_center(target)

    def _resolve_collisions_x(self, tilemap: TileMap) -> None:
        player_rect = self.rect
        for solid in tilemap.get_solid_rects_near(player_rect):
            if not player_rect.colliderect(solid):
                continue
            if self.vel.x > 0:
                self.pos.x = solid.left - self.size
            elif self.vel.x < 0:
                self.pos.x = solid.right
            self.vel.x = 0.0
            player_rect = self.rect

    def _resolve_collisions_y(self, tilemap: TileMap) -> None:
        player_rect = self.rect
        for solid in tilemap.get_solid_rects_near(player_rect):
            if not player_rect.colliderect(solid):
                continue
            if self.vel.y > 0:
                self.pos.y = solid.top - self.size
            elif self.vel.y < 0:
                self.pos.y = solid.bottom
            self.vel.y = 0.0
            player_rect = self.rect
