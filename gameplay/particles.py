from __future__ import annotations

import random
from dataclasses import dataclass

import pygame


@dataclass(slots=True)
class Particle:
    pos: pygame.Vector2
    vel: pygame.Vector2
    life_sec: float
    max_life_sec: float
    size: int
    color: tuple[int, int, int]


class ParticleSystem:
    def __init__(self) -> None:
        self.particles: list[Particle] = []

    def spawn_burst(
        self,
        center: tuple[float, float],
        count: int,
        color: tuple[int, int, int],
        speed_min: float,
        speed_max: float,
        life_min: float,
        life_max: float,
    ) -> None:
        for _ in range(count):
            angle = random.uniform(0.0, 360.0)
            speed = random.uniform(speed_min, speed_max)
            vel = pygame.Vector2(speed, 0.0).rotate(angle)
            life = random.uniform(life_min, life_max)
            size = random.randint(2, 5)
            jitter = random.randint(-20, 20)
            r = max(0, min(255, color[0] + jitter))
            g = max(0, min(255, color[1] + jitter))
            b = max(0, min(255, color[2] + jitter))
            self.particles.append(
                Particle(
                    pos=pygame.Vector2(center),
                    vel=vel,
                    life_sec=life,
                    max_life_sec=life,
                    size=size,
                    color=(r, g, b),
                )
            )

    def update(self, dt: float) -> None:
        alive: list[Particle] = []
        for particle in self.particles:
            particle.life_sec -= dt
            if particle.life_sec <= 0.0:
                continue
            particle.pos += particle.vel * dt
            particle.vel *= 0.95
            alive.append(particle)
        self.particles = alive

    def draw(self, surface: pygame.Surface, camera_offset: pygame.Vector2) -> None:
        ox = int(camera_offset.x)
        oy = int(camera_offset.y)
        for particle in self.particles:
            life_ratio = particle.life_sec / particle.max_life_sec
            alpha = int(255 * life_ratio)
            size = max(1, int(particle.size * life_ratio))
            draw_color = (*particle.color, alpha)
            rect = pygame.Rect(
                int(particle.pos.x + ox),
                int(particle.pos.y + oy),
                size,
                size,
            )
            pygame.draw.rect(surface, draw_color, rect)

