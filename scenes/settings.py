from __future__ import annotations

import pygame

from core.utils import UIButton, clamp, draw_button


class SettingsScene:
    def __init__(self, game) -> None:
        self.game = game
        self.title_font = self.game.assets.font(46, bold=True)
        self.text_font = self.game.assets.font(28)
        self.button_font = self.game.assets.font(24)
        self.fade_alpha = 180.0
        self.back_button = UIButton(
            rect=pygame.Rect(36, 476, 180, 44), label="닫기", value="back", enabled=True
        )

    def handle_event(self, event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.game.scene_manager.pop()
            return

        click_pos = None
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            click_pos = self.game.window_to_base(event.pos)
        elif event.type == pygame.FINGERDOWN:
            click_pos = self.game.finger_to_base(event.x, event.y)

        if click_pos is None:
            return

        if self.back_button.rect.collidepoint(click_pos):
            self.game.scene_manager.pop()
            return

        self._handle_setting_click(click_pos)

    def _handle_setting_click(self, pos: tuple[int, int]) -> None:
        rows = self._setting_rows()
        volume_rect = rows["master_volume"]
        if volume_rect.collidepoint(pos):
            if pos[0] < volume_rect.centerx:
                value = int(self.game.settings["master_volume"]) - 10
            else:
                value = int(self.game.settings["master_volume"]) + 10
            self.game.set_setting("master_volume", int(clamp(value, 0, 100)))
            return

        fullscreen_rect = rows["fullscreen"]
        if fullscreen_rect.collidepoint(pos):
            self.game.set_setting("fullscreen", not bool(self.game.settings["fullscreen"]))
            return

        scale_rect = rows["screen_scale"]
        if scale_rect.collidepoint(pos):
            current = int(self.game.settings["screen_scale"])
            self.game.set_setting("screen_scale", 1 if current >= 3 else current + 1)
            return

        shake_rect = rows["screen_shake"]
        if shake_rect.collidepoint(pos):
            self.game.set_setting("screen_shake", not bool(self.game.settings["screen_shake"]))

    def _setting_rows(self) -> dict[str, pygame.Rect]:
        start_x = 180
        start_y = 150
        width = 600
        height = 64
        gap = 16
        return {
            "master_volume": pygame.Rect(start_x, start_y + 0 * (height + gap), width, height),
            "fullscreen": pygame.Rect(start_x, start_y + 1 * (height + gap), width, height),
            "screen_scale": pygame.Rect(start_x, start_y + 2 * (height + gap), width, height),
            "screen_shake": pygame.Rect(start_x, start_y + 3 * (height + gap), width, height),
        }

    def update(self, dt: float) -> None:
        self.fade_alpha = max(0.0, self.fade_alpha - dt * 500.0)

    def render(self, surface: pygame.Surface) -> None:
        self._draw_background(surface)
        title = self.title_font.render("설정", True, (240, 240, 244))
        surface.blit(title, title.get_rect(center=(480, 72)))

        rows = self._setting_rows()
        mouse_pos = self.game.window_to_base(pygame.mouse.get_pos())
        labels = {
            "master_volume": "마스터 볼륨",
            "fullscreen": "전체화면",
            "screen_scale": "화면 배율",
            "screen_shake": "화면 흔들림",
        }
        values = {
            "master_volume": f"{int(self.game.settings['master_volume'])}",
            "fullscreen": "켜짐" if self.game.settings["fullscreen"] else "꺼짐",
            "screen_scale": f"{int(self.game.settings['screen_scale'])}x",
            "screen_shake": "켜짐" if self.game.settings["screen_shake"] else "꺼짐",
        }

        for key, rect in rows.items():
            hovered = mouse_pos is not None and rect.collidepoint(mouse_pos)
            color = (78, 103, 148) if hovered else (58, 76, 110)
            pygame.draw.rect(surface, color, rect, border_radius=10)
            pygame.draw.rect(surface, (23, 30, 44), rect, width=2, border_radius=10)
            label_surf = self.text_font.render(labels[key], True, (234, 234, 238))
            value_surf = self.text_font.render(values[key], True, (198, 229, 255))
            surface.blit(label_surf, label_surf.get_rect(midleft=(rect.left + 22, rect.centery)))
            surface.blit(value_surf, value_surf.get_rect(midright=(rect.right - 24, rect.centery)))

        hint = self.button_font.render(
            "볼륨: 왼쪽 클릭 감소 / 오른쪽 클릭 증가, 나머지는 클릭으로 전환",
            True,
            (189, 202, 228),
        )
        surface.blit(hint, hint.get_rect(center=(480, 444)))

        hover_back = mouse_pos is not None and self.back_button.rect.collidepoint(mouse_pos)
        draw_button(surface, self.button_font, self.back_button, hover_back)

        if self.fade_alpha > 0:
            overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, int(self.fade_alpha)))
            surface.blit(overlay, (0, 0))

    @staticmethod
    def _draw_background(surface: pygame.Surface) -> None:
        for y in range(surface.get_height()):
            t = y / max(1, surface.get_height() - 1)
            color = (13 + int(9 * t), 18 + int(15 * t), 34 + int(30 * t))
            pygame.draw.line(surface, color, (0, y), (surface.get_width(), y))
        pygame.draw.circle(surface, (28, 46, 84), (190, 90), 120)
        pygame.draw.circle(surface, (35, 60, 102), (820, 450), 180)

