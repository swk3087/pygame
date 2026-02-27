from __future__ import annotations

import random

import pygame

from core.config import (
    BASE_H,
    BASE_W,
    CLICK_PARTICLE_MAX,
    CLICK_PARTICLE_MIN,
    ROTATE_COOLDOWN_SEC,
    TELEPORT_FLASH_SEC,
)
from core.utils import UIButton, draw_button
from gameplay.particles import ParticleSystem
from gameplay.player import Player
from gameplay.portal import PortalSystem
from gameplay.tilemap import MapValidationError, TileMap


class GameScene:
    GRAVITY_DIRS = [
        pygame.Vector2(0.0, 1.0),
        pygame.Vector2(-1.0, 0.0),
        pygame.Vector2(0.0, -1.0),
        pygame.Vector2(1.0, 0.0),
    ]

    def __init__(self, game, level_index: int) -> None:
        self.game = game
        self.level_index = level_index
        self.level_entry = self.game.level_entries[level_index]
        self.title_font = self.game.assets.font(30, bold=True)
        self.hud_font = self.game.assets.font(22)
        self.info_font = self.game.assets.font(20)
        self.pause_font = self.game.assets.font(28, bold=True)
        self.button_font = self.game.assets.font(24)

        self.fade_alpha = 180.0
        self.load_error: str | None = None
        self.error_back_button = UIButton(
            rect=pygame.Rect(390, 324, 180, 52), label="레벨 선택", value="back", enabled=True
        )

        self.paused = False
        self.pause_buttons = self._build_pause_buttons()
        self.show_ui_text = False
        self.zero_key_held = False

        self.gravity_dir = 0
        self.rotate_cooldown = 0.0
        self.elapsed_sec = 0.0
        self.click_count = 0
        self.death_count = 0
        self.teleport_flash_sec = 0.0
        self.screen_shake_timer = 0.0
        self.screen_shake_strength = 0.0

        self.particles = ParticleSystem()
        self.cleared = False

        self.tilemap: TileMap | None = None
        self.portal_system: PortalSystem | None = None
        self.player: Player | None = None
        self.map_draw_origin = pygame.Vector2(0.0, 0.0)

        self._load_map()

    def _load_map(self) -> None:
        try:
            tilemap = TileMap.from_json(self.level_entry.path)
        except MapValidationError as exc:
            self.load_error = str(exc)
            print(f"[map] load failed: {self.level_entry.path.name}: {exc}")
            return

        self.tilemap = tilemap
        self.player = Player(tilemap.spawn_px, tilemap.tile_size)
        self.portal_system = PortalSystem(tilemap.tile_size, tilemap.portal_groups)
        map_w, map_h = tilemap.pixel_size
        self.map_draw_origin = pygame.Vector2((BASE_W - map_w) / 2.0, (BASE_H - map_h) / 2.0)

    def _build_pause_buttons(self) -> list[UIButton]:
        center_x = 480
        top = 180
        width = 260
        height = 52
        gap = 10
        labels = [
            ("계속", "resume"),
            ("다시시작", "restart"),
            ("레벨선택", "levels"),
            ("메인메뉴", "menu"),
        ]
        buttons: list[UIButton] = []
        for i, (label, value) in enumerate(labels):
            rect = pygame.Rect(0, 0, width, height)
            rect.centerx = center_x
            rect.y = top + i * (height + gap)
            buttons.append(UIButton(rect=rect, label=label, value=value, enabled=True))
        return buttons

    def handle_event(self, event) -> None:
        if event.type == pygame.KEYUP and event.key in {pygame.K_0, pygame.K_KP0}:
            self.zero_key_held = False
            return

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.load_error:
                    self.game.open_level_select()
                else:
                    self.paused = not self.paused
                return
            if event.key in {pygame.K_0, pygame.K_KP0}:
                self.zero_key_held = True
                self.show_ui_text = not self.show_ui_text
                return
            if event.key == pygame.K_r and not self.load_error:
                self.game.start_level(self.level_index)
                return

        click_pos = None
        rotate_delta = 0
        if event.type == pygame.MOUSEBUTTONDOWN and event.button in {1, 3}:
            click_pos = self.game.window_to_base(event.pos)
            if event.button == 1:
                rotate_delta = 1
            elif event.button == 3 and self.zero_key_held:
                rotate_delta = -1
        elif event.type == pygame.FINGERDOWN:
            click_pos = self.game.finger_to_base(event.x, event.y)
            if click_pos is not None:
                rotate_delta = 1 if click_pos[0] < BASE_W // 2 else -1
        if click_pos is None:
            return

        if self.load_error:
            if self.error_back_button.rect.collidepoint(click_pos):
                self.game.open_level_select()
            return

        if self.paused:
            self._handle_pause_click(click_pos)
            return

        if rotate_delta != 0:
            self._try_rotate_gravity(rotate_delta)

    def _handle_pause_click(self, click_pos: tuple[int, int]) -> None:
        for button in self.pause_buttons:
            if button.rect.collidepoint(click_pos):
                if button.value == "resume":
                    self.paused = False
                elif button.value == "restart":
                    self.game.start_level(self.level_index)
                elif button.value == "levels":
                    self.game.open_level_select()
                elif button.value == "menu":
                    self.game.open_main_menu()
                return

    def _try_rotate_gravity(self, rotate_delta: int) -> None:
        if self.rotate_cooldown > 0.0 or self.player is None or self.tilemap is None:
            return
        if rotate_delta > 0:
            self.gravity_dir = (self.gravity_dir + 1) % 4
            self.player.rotate_velocity_ccw()
        else:
            self.gravity_dir = (self.gravity_dir - 1) % 4
            self.player.rotate_velocity_cw()
        self.player.snap_to_nearest_tile(self.tilemap)
        self.rotate_cooldown = ROTATE_COOLDOWN_SEC
        self.click_count += 1
        self.game.assets.play("rotate")
        self._add_shake(0.08, 2.8)
        self.particles.spawn_burst(
            center=self.player.center,
            count=random.randint(CLICK_PARTICLE_MIN, CLICK_PARTICLE_MAX),
            color=(145, 191, 255),
            speed_min=80.0,
            speed_max=210.0,
            life_min=0.16,
            life_max=0.42,
        )

    def update(self, dt: float) -> None:
        self.fade_alpha = max(0.0, self.fade_alpha - dt * 500.0)
        self.rotate_cooldown = max(0.0, self.rotate_cooldown - dt)
        self.teleport_flash_sec = max(0.0, self.teleport_flash_sec - dt)
        self.screen_shake_timer = max(0.0, self.screen_shake_timer - dt)

        if self.load_error or self.paused or self.cleared:
            self.particles.update(dt)
            return

        if self.tilemap is None or self.player is None:
            return

        self.elapsed_sec += dt
        gravity_vec = self.GRAVITY_DIRS[self.gravity_dir]
        self.player.update(dt, gravity_vec, self.tilemap)

        player_rect = self.player.rect
        for spike_rect in self.tilemap.spike_tiles:
            if player_rect.colliderect(spike_rect):
                self.death_count += 1
                self.player.respawn(self.tilemap.spawn_px)
                self._add_shake(0.1, 4.5)
                self.particles.spawn_burst(
                    center=self.player.center,
                    count=14,
                    color=(214, 86, 86),
                    speed_min=70.0,
                    speed_max=220.0,
                    life_min=0.15,
                    life_max=0.38,
                )
                break

        if self.portal_system is not None:
            tp = self.portal_system.try_teleport(self.player.rect, self.elapsed_sec)
            if tp is not None:
                self.player.set_center(tp.destination_center)
                self.teleport_flash_sec = TELEPORT_FLASH_SEC
                self._add_shake(0.06, 3.6)
                self.game.assets.play("teleport")
                self.particles.spawn_burst(
                    center=self.player.center,
                    count=18,
                    color=(108, 238, 224),
                    speed_min=90.0,
                    speed_max=260.0,
                    life_min=0.18,
                    life_max=0.45,
                )

        for goal_rect in self.tilemap.goal_tiles:
            if self.player.rect.colliderect(goal_rect):
                self._complete_level()
                break

        self.particles.update(dt)

    def _complete_level(self) -> None:
        if self.cleared or self.tilemap is None:
            return
        self.cleared = True
        self.game.assets.play("clear")
        self.particles.spawn_burst(
            center=self.player.center if self.player else (0, 0),
            count=28,
            color=(140, 245, 158),
            speed_min=100.0,
            speed_max=280.0,
            life_min=0.2,
            life_max=0.5,
        )
        result = {
            "level_index": self.level_index,
            "level_id": self.tilemap.level_id,
            "level_name": self.tilemap.level_name,
            "clicks": self.click_count,
            "time_sec": self.elapsed_sec,
            "deaths": self.death_count,
        }
        self.game.complete_level(result)

    def _add_shake(self, duration: float, strength: float) -> None:
        self.screen_shake_timer = max(self.screen_shake_timer, duration)
        self.screen_shake_strength = max(self.screen_shake_strength, strength)

    def _camera_offset(self) -> pygame.Vector2:
        offset = self.map_draw_origin.copy()
        if not self.game.settings.get("screen_shake", True):
            return offset
        if self.screen_shake_timer <= 0.0:
            return offset
        jitter = self.screen_shake_strength * (self.screen_shake_timer / 0.12)
        offset.x += random.uniform(-jitter, jitter)
        offset.y += random.uniform(-jitter, jitter)
        return offset

    def render(self, surface: pygame.Surface) -> None:
        self._draw_background(surface)
        if self.load_error:
            self._draw_load_error(surface)
            if self.fade_alpha > 0:
                self._draw_fade(surface)
            return

        if self.tilemap is None or self.player is None:
            return

        camera_offset = self._camera_offset()
        self.tilemap.draw(surface, self.elapsed_sec, camera_offset)
        self.particles.draw(surface, camera_offset)
        self._draw_player(surface, camera_offset)
        if self.show_ui_text:
            self._draw_hud(surface)

        if self.teleport_flash_sec > 0:
            alpha = int(180 * (self.teleport_flash_sec / TELEPORT_FLASH_SEC))
            overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
            overlay.fill((220, 255, 255, alpha))
            surface.blit(overlay, (0, 0))

        if self.paused:
            self._draw_pause_overlay(surface)

        if self.fade_alpha > 0:
            self._draw_fade(surface)

    def _draw_hud(self, surface: pygame.Surface) -> None:
        if self.tilemap is None:
            return
        left_text = (
            f"{self.level_index + 1:03d} {self.tilemap.level_name}   "
            f"클릭 {self.click_count}   시간 {self.elapsed_sec:.2f}s   데스 {self.death_count}"
        )
        gravity_texts = ["중력: 아래", "중력: 왼쪽", "중력: 위", "중력: 오른쪽"]
        hud = self.hud_font.render(left_text, True, (236, 236, 240))
        grav = self.hud_font.render(gravity_texts[self.gravity_dir], True, (173, 205, 249))
        surface.blit(hud, (18, 14))
        surface.blit(grav, (18, 40))

    def _draw_player(self, surface: pygame.Surface, camera_offset: pygame.Vector2) -> None:
        if self.player is None:
            return
        rect = self.player.rect.move(int(camera_offset.x), int(camera_offset.y))
        pygame.draw.rect(surface, (255, 206, 92), rect, border_radius=4)
        pygame.draw.rect(surface, (72, 58, 26), rect, width=2, border_radius=4)

    def _draw_pause_overlay(self, surface: pygame.Surface) -> None:
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((4, 6, 12, 170))
        surface.blit(overlay, (0, 0))

        title = self.pause_font.render("일시정지", True, (245, 245, 248))
        surface.blit(title, title.get_rect(center=(480, 132)))

        hover = self.game.window_to_base(pygame.mouse.get_pos())
        for button in self.pause_buttons:
            hovered = hover is not None and button.rect.collidepoint(hover)
            draw_button(surface, self.button_font, button, hovered)

    def _draw_load_error(self, surface: pygame.Surface) -> None:
        msg_title = self.title_font.render("맵 로드 실패", True, (242, 122, 122))
        msg_body = self.info_font.render(self.load_error or "알 수 없는 오류", True, (238, 214, 214))
        hint = self.info_font.render("문제를 수정한 뒤 다시 시도하세요.", True, (198, 176, 176))
        surface.blit(msg_title, msg_title.get_rect(center=(480, 210)))
        surface.blit(msg_body, msg_body.get_rect(center=(480, 254)))
        surface.blit(hint, hint.get_rect(center=(480, 284)))

        hover = self.game.window_to_base(pygame.mouse.get_pos())
        hovered = hover is not None and self.error_back_button.rect.collidepoint(hover)
        draw_button(surface, self.button_font, self.error_back_button, hovered)

    @staticmethod
    def _draw_background(surface: pygame.Surface) -> None:
        for y in range(surface.get_height()):
            t = y / max(1, surface.get_height() - 1)
            color = (10 + int(10 * t), 14 + int(16 * t), 24 + int(24 * t))
            pygame.draw.line(surface, color, (0, y), (surface.get_width(), y))

    def _draw_fade(self, surface: pygame.Surface) -> None:
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, int(self.fade_alpha)))
        surface.blit(overlay, (0, 0))
