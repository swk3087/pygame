from __future__ import annotations

import pygame

from core.config import UI_SCALE_OPTIONS
from core.utils import UIButton, clamp, draw_button


class SettingsScene:
    BOOL_KEYS = {
        "fullscreen",
        "screen_shake",
        "show_hud_while_zero_held",
        "high_contrast_ui",
        "reduced_motion",
    }

    LABELS = {
        "master_volume": "마스터 볼륨",
        "fullscreen": "전체화면",
        "screen_scale": "화면 배율",
        "screen_shake": "화면 흔들림",
        "show_hud_while_zero_held": "HUD 0키 홀드 표시",
        "high_contrast_ui": "고대비 UI",
        "reduced_motion": "모션 감소",
        "ui_scale_percent": "UI 글자 크기",
    }

    def __init__(self, game) -> None:
        self.game = game
        self.fade_alpha = 180.0
        self._reload_fonts()
        self.back_button = UIButton(
            rect=pygame.Rect(36, 476, 180, 44), label="닫기", value="back", enabled=True
        )
        self._row_keys = [
            "master_volume",
            "fullscreen",
            "screen_scale",
            "screen_shake",
            "show_hud_while_zero_held",
            "high_contrast_ui",
            "reduced_motion",
            "ui_scale_percent",
        ]

    def _reload_fonts(self) -> None:
        self.title_font = self.game.assets.font(46, bold=True)
        self.text_font = self.game.assets.font(20)
        self.button_font = self.game.assets.font(22)
        self.info_font = self.game.assets.font(18)

    def on_settings_changed(self) -> None:
        self._reload_fonts()

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

    def _setting_rows(self) -> dict[str, pygame.Rect]:
        start_x = 160
        start_y = 88
        width = 640
        height = 32
        gap = 8
        rows: dict[str, pygame.Rect] = {}
        for idx, key in enumerate(self._row_keys):
            rows[key] = pygame.Rect(start_x, start_y + idx * (height + gap), width, height)
        return rows

    def _handle_setting_click(self, pos: tuple[int, int]) -> None:
        rows = self._setting_rows()
        for key, rect in rows.items():
            if not rect.collidepoint(pos):
                continue
            if key == "master_volume":
                if pos[0] < rect.centerx:
                    value = int(self.game.settings["master_volume"]) - 10
                else:
                    value = int(self.game.settings["master_volume"]) + 10
                self.game.set_setting("master_volume", int(clamp(value, 0, 100)))
                return
            if key == "screen_scale":
                current = int(self.game.settings["screen_scale"])
                self.game.set_setting("screen_scale", 1 if current >= 3 else current + 1)
                return
            if key == "ui_scale_percent":
                current = int(self.game.settings["ui_scale_percent"])
                current_idx = UI_SCALE_OPTIONS.index(current) if current in UI_SCALE_OPTIONS else 1
                if pos[0] < rect.centerx:
                    next_idx = (current_idx - 1) % len(UI_SCALE_OPTIONS)
                else:
                    next_idx = (current_idx + 1) % len(UI_SCALE_OPTIONS)
                self.game.set_setting("ui_scale_percent", UI_SCALE_OPTIONS[next_idx])
                return
            if key in self.BOOL_KEYS:
                self.game.set_setting(key, not bool(self.game.settings[key]))
                return

    def _value_text(self, key: str) -> str:
        if key == "master_volume":
            return f"{int(self.game.settings['master_volume'])}"
        if key == "screen_scale":
            return f"{int(self.game.settings['screen_scale'])}x"
        if key == "ui_scale_percent":
            return f"{int(self.game.settings['ui_scale_percent'])}%"
        return "켜짐" if bool(self.game.settings[key]) else "꺼짐"

    def update(self, dt: float) -> None:
        self.fade_alpha = max(0.0, self.fade_alpha - dt * 500.0)

    def render(self, surface: pygame.Surface) -> None:
        self._draw_background(surface)
        title = self.title_font.render("설정", True, (240, 240, 244))
        surface.blit(title, title.get_rect(center=(480, 54)))

        rows = self._setting_rows()
        mouse_pos = self.game.window_to_base(pygame.mouse.get_pos())
        use_hc = bool(self.game.settings.get("high_contrast_ui", False))

        for key, rect in rows.items():
            hovered = mouse_pos is not None and rect.collidepoint(mouse_pos)
            if use_hc:
                color = (36, 36, 36) if hovered else (28, 28, 28)
                edge = (220, 220, 220)
                label_color = (245, 245, 245)
                value_color = (255, 234, 128)
            else:
                color = (78, 103, 148) if hovered else (58, 76, 110)
                edge = (23, 30, 44)
                label_color = (234, 234, 238)
                value_color = (198, 229, 255)
            pygame.draw.rect(surface, color, rect, border_radius=8)
            pygame.draw.rect(surface, edge, rect, width=2, border_radius=8)
            label_surf = self.text_font.render(self.LABELS[key], True, label_color)
            value_surf = self.text_font.render(self._value_text(key), True, value_color)
            surface.blit(label_surf, label_surf.get_rect(midleft=(rect.left + 16, rect.centery)))
            surface.blit(value_surf, value_surf.get_rect(midright=(rect.right - 16, rect.centery)))

        hint = self.info_font.render(
            "볼륨/UI크기: 좌측 감소, 우측 증가 | 나머지: 클릭 토글",
            True,
            (189, 202, 228),
        )
        surface.blit(hint, hint.get_rect(center=(480, 458)))

        hover_back = mouse_pos is not None and self.back_button.rect.collidepoint(mouse_pos)
        draw_button(
            surface,
            self.button_font,
            self.back_button,
            hover_back,
            high_contrast=use_hc,
        )

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
