from __future__ import annotations

import pygame

from core.utils import UIButton, draw_button


class ResultsScene:
    def __init__(self, game, result_data: dict) -> None:
        self.game = game
        self.result_data = result_data
        self.title_font = self.game.assets.font(54, bold=True)
        self.text_font = self.game.assets.font(30)
        self.info_font = self.game.assets.font(22)
        self.button_font = self.game.assets.font(24)
        self.fade_alpha = 180.0
        self.buttons = self._build_buttons()

    def _build_buttons(self) -> list[UIButton]:
        level_index = int(self.result_data.get("level_index", 0))
        has_next = level_index + 1 < len(self.game.level_entries)
        labels = [
            ("다음", "next", has_next),
            ("재시도", "retry", True),
            ("뒤로", "back", True),
        ]
        width = 180
        height = 54
        gap = 20
        total_w = 3 * width + 2 * gap
        start_x = (960 - total_w) // 2
        y = 390
        buttons: list[UIButton] = []
        for i, (label, value, enabled) in enumerate(labels):
            rect = pygame.Rect(start_x + i * (width + gap), y, width, height)
            buttons.append(UIButton(rect=rect, label=label, value=value, enabled=enabled))
        return buttons

    def handle_event(self, event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.game.open_level_select()
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
        level_index = int(self.result_data.get("level_index", 0))
        if value == "next":
            self.game.start_level(level_index + 1)
        elif value == "retry":
            self.game.start_level(level_index)
        elif value == "back":
            self.game.open_level_select()

    def update(self, dt: float) -> None:
        self.fade_alpha = max(0.0, self.fade_alpha - dt * 500.0)

    def render(self, surface: pygame.Surface) -> None:
        self._draw_background(surface)
        title = self.title_font.render("클리어!", True, (216, 246, 165))
        surface.blit(title, title.get_rect(center=(480, 110)))

        level_name = str(self.result_data.get("level_name", "Unknown"))
        clicks = int(self.result_data.get("clicks", 0))
        time_sec = float(self.result_data.get("time_sec", 0.0))
        deaths = int(self.result_data.get("deaths", 0))
        level_id = str(self.result_data.get("level_id", ""))

        lines = [
            f"레벨: {level_name}",
            f"클릭 수: {clicks}",
            f"클리어 시간: {time_sec:.2f}초",
            f"데스 수: {deaths}",
        ]
        best = self.game.save_data.get("best_records", {}).get(level_id)
        if isinstance(best, dict):
            best_line = (
                f"최고 기록 - 클릭 {int(best.get('clicks', 0))} / 시간 {float(best.get('time_sec', 0.0)):.2f}초"
            )
            lines.append(best_line)

        for idx, line in enumerate(lines):
            color = (236, 236, 242) if idx < 4 else (176, 222, 255)
            surf = self.text_font.render(line, True, color)
            surface.blit(surf, surf.get_rect(center=(480, 188 + idx * 44)))

        hover = self.game.window_to_base(pygame.mouse.get_pos())
        for button in self.buttons:
            hovered = hover is not None and button.rect.collidepoint(hover)
            draw_button(surface, self.button_font, button, hovered)

        info = self.info_font.render("ESC: 레벨 선택으로 돌아가기", True, (180, 198, 226))
        surface.blit(info, info.get_rect(center=(480, 486)))

        if self.fade_alpha > 0:
            overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, int(self.fade_alpha)))
            surface.blit(overlay, (0, 0))

    @staticmethod
    def _draw_background(surface: pygame.Surface) -> None:
        for y in range(surface.get_height()):
            t = y / max(1, surface.get_height() - 1)
            color = (13 + int(10 * t), 22 + int(16 * t), 18 + int(16 * t))
            pygame.draw.line(surface, color, (0, y), (surface.get_width(), y))
        pygame.draw.circle(surface, (32, 80, 46), (160, 120), 140)
        pygame.draw.circle(surface, (42, 100, 58), (820, 420), 180)

