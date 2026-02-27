from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import pygame


def clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def rotate_vec_ccw(vec: pygame.Vector2) -> pygame.Vector2:
    return pygame.Vector2(-vec.y, vec.x)


def rotate_vec_cw(vec: pygame.Vector2) -> pygame.Vector2:
    return pygame.Vector2(vec.y, -vec.x)


def clamp_vec_magnitude(vec: pygame.Vector2, max_length: float) -> pygame.Vector2:
    length = vec.length()
    if length <= max_length or length == 0.0:
        return vec
    return vec * (max_length / length)


def safe_int(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


@dataclass(slots=True)
class UIButton:
    rect: pygame.Rect
    label: str
    value: str
    enabled: bool = True


def draw_button(
    surface: pygame.Surface,
    font: pygame.font.Font,
    button: UIButton,
    hovered: bool,
    high_contrast: bool = False,
) -> None:
    if not button.enabled:
        if high_contrast:
            bg = (30, 30, 30)
            fg = (168, 168, 168)
        else:
            bg = (60, 60, 60)
            fg = (130, 130, 130)
    elif hovered:
        if high_contrast:
            bg = (248, 232, 112)
            fg = (12, 12, 12)
        else:
            bg = (92, 112, 158)
            fg = (245, 245, 245)
    else:
        if high_contrast:
            bg = (24, 24, 24)
            fg = (248, 248, 248)
        else:
            bg = (56, 70, 104)
            fg = (230, 230, 230)
    pygame.draw.rect(surface, bg, button.rect, border_radius=8)
    edge = (248, 248, 248) if high_contrast else (20, 24, 32)
    pygame.draw.rect(surface, edge, button.rect, width=2, border_radius=8)
    text = font.render(button.label, True, fg)
    text_rect = text.get_rect(center=button.rect.center)
    surface.blit(text, text_rect)


def rand_unit_vec() -> pygame.Vector2:
    angle = math.radians(pygame.time.get_ticks() % 360)
    return pygame.Vector2(math.cos(angle), math.sin(angle))
