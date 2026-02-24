from __future__ import annotations

import pygame

from core.config import GRAVITY_ACC, MAX_SPEED
from core.utils import clamp_vec_magnitude, rotate_vec_ccw, rotate_vec_cw
from gameplay.tilemap import TileMap


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
