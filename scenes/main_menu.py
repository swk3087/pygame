from __future__ import annotations

import pygame

from core.utils import UIButton, draw_button


class MainMenuScene:
    def __init__(self, game) -> None:
        self.game = game
        self._reload_fonts()
        self.fade_alpha = 180.0
        self.buttons = self._build_buttons()

    def _reload_fonts(self) -> None:
        self.title_font = self.game.assets.font(60, bold=True)
        self.button_font = self.game.assets.font(30)
        self.info_font = self.game.assets.font(22)

    def on_resume(self) -> None:
        self._reload_fonts()
        self.buttons = self._build_buttons()

    def _build_buttons(self) -> list[UIButton]:
        center_x = 480
        top = 190
        width = 300
        height = 56
        gap = 14
        labels = [
            ("시작", "start"),
            ("레벨 선택", "level_select"),
            ("설정", "settings"),
            ("종료", "quit"),
        ]
        buttons: list[UIButton] = []
        for i, (label, value) in enumerate(labels):
            rect = pygame.Rect(0, 0, width, height)
            rect.centerx = center_x
            rect.y = top + i * (height + gap)
            buttons.append(UIButton(rect=rect, label=label, value=value, enabled=True))
        if not self.game.level_entries:
            for button in buttons:
                if button.value in {"start", "level_select"}:
                    button.enabled = False
        return buttons

    def handle_event(self, event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.game.request_quit()
            return

        click_pos = None
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            click_pos = self.game.window_to_base(event.pos)
        elif event.type == pygame.FINGERDOWN:
            click_pos = self.game.finger_to_base(event.x, event.y)

        if click_pos is None:
            return
        for button in self.buttons:
            if button.enabled and button.rect.collidepoint(click_pos):
                self._activate(button.value)
                return

    def _activate(self, value: str) -> None:
        if value == "start":
            self.game.start_first_playable_level()
        elif value == "level_select":
            self.game.open_level_select()
        elif value == "settings":
            self.game.open_settings()
        elif value == "quit":
            self.game.request_quit()

    def update(self, dt: float) -> None:
        self.fade_alpha = max(0.0, self.fade_alpha - dt * 500.0)

    def render(self, surface: pygame.Surface) -> None:
        self._draw_background(surface)

        title = self.title_font.render("Gravity Rotate", True, (240, 240, 245))
        title_rect = title.get_rect(center=(480, 88))
        surface.blit(title, title_rect)

        subtitle = self.info_font.render(
            "좌클릭 CCW / 우클릭 CW(기본: 0키 홀드 필요)",
            True,
            (178, 193, 228),
        )
        subtitle_rect = subtitle.get_rect(center=(480, 132))
        surface.blit(subtitle, subtitle_rect)

        hover_pos = self.game.window_to_base(pygame.mouse.get_pos())
        high_contrast = bool(self.game.settings.get("high_contrast_ui", False))
        for button in self.buttons:
            hovered = hover_pos is not None and button.rect.collidepoint(hover_pos)
            draw_button(surface, self.button_font, button, hovered, high_contrast=high_contrast)

        if not self.game.level_entries:
            warn = self.info_font.render("map 폴더에 레벨 JSON이 없습니다.", True, (250, 164, 164))
            warn_rect = warn.get_rect(center=(480, 472))
            surface.blit(warn, warn_rect)

        if self.fade_alpha > 0:
            overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, int(self.fade_alpha)))
            surface.blit(overlay, (0, 0))

    @staticmethod
    def _draw_background(surface: pygame.Surface) -> None:
        for y in range(surface.get_height()):
            t = y / max(1, surface.get_height() - 1)
            r = int(14 + 14 * t)
            g = int(18 + 24 * t)
            b = int(30 + 38 * t)
            pygame.draw.line(surface, (r, g, b), (0, y), (surface.get_width(), y))
        pygame.draw.circle(surface, (20, 42, 86), (90, 80), 120, width=0)
        pygame.draw.circle(surface, (31, 63, 92), (880, 430), 160, width=0)
