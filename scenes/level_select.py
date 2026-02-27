from __future__ import annotations

import pygame

from core.utils import UIButton, draw_button


class LevelSelectScene:
    def __init__(self, game) -> None:
        self.game = game
        self.title_font = self.game.assets.font(46, bold=True)
        self.button_font = self.game.assets.font(24)
        self.info_font = self.game.assets.font(20)
        self.fade_alpha = 180.0
        self.level_buttons: list[UIButton] = []
        self.list_rect = pygame.Rect(120, 140, 720, 320)
        self._scroll_offset = 0.0
        self._max_scroll = 0.0
        self._row_height = 54
        self._row_gap = 10
        self.back_button = UIButton(
            rect=pygame.Rect(36, 476, 180, 44),
            label="뒤로",
            value="back",
            enabled=True,
        )
        self._rebuild()

    def on_resume(self) -> None:
        self._rebuild()

    def _rebuild(self) -> None:
        self.level_buttons.clear()
        unlocked = int(self.game.save_data.get("unlocked_level_count", 1))
        start_x = self.list_rect.x
        start_y = self.list_rect.y
        width = self.list_rect.width
        height = self._row_height
        gap = self._row_gap
        for entry in self.game.level_entries:
            label = f"{entry.index + 1:03d}. {entry.name}"
            enabled = entry.index < unlocked
            if not enabled:
                label = f"{label}  (잠김)"
            rect = pygame.Rect(start_x, start_y + entry.index * (height + gap), width, height)
            self.level_buttons.append(
                UIButton(rect=rect, label=label, value=str(entry.index), enabled=enabled)
            )
        self._refresh_scroll_limits()

    def _refresh_scroll_limits(self) -> None:
        if not self.level_buttons:
            self._max_scroll = 0.0
            self._scroll_offset = 0.0
            return
        content_h = len(self.level_buttons) * (self._row_height + self._row_gap) - self._row_gap
        self._max_scroll = max(0.0, float(content_h - self.list_rect.height))
        self._scroll_offset = max(0.0, min(self._scroll_offset, self._max_scroll))

    def _scroll_by(self, delta: float) -> None:
        if self._max_scroll <= 0.0:
            return
        self._scroll_offset = max(0.0, min(self._max_scroll, self._scroll_offset + delta))

    def handle_event(self, event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.game.open_main_menu()
                return
            if event.key == pygame.K_DOWN:
                self._scroll_by(40)
                return
            if event.key == pygame.K_UP:
                self._scroll_by(-40)
                return
            if event.key == pygame.K_PAGEDOWN:
                self._scroll_by(self.list_rect.height * 0.8)
                return
            if event.key == pygame.K_PAGEUP:
                self._scroll_by(-self.list_rect.height * 0.8)
                return

        if event.type == pygame.MOUSEWHEEL:
            self._scroll_by(-event.y * 36)
            return

        click_pos = None
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            click_pos = self.game.window_to_base(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 4:
            self._scroll_by(-36)
            return
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 5:
            self._scroll_by(36)
            return
        elif event.type == pygame.FINGERDOWN:
            click_pos = self.game.finger_to_base(event.x, event.y)
        if click_pos is None:
            return

        if self.back_button.rect.collidepoint(click_pos):
            self.game.open_main_menu()
            return

        if not self.list_rect.collidepoint(click_pos):
            return

        for button in self.level_buttons:
            draw_rect = button.rect.move(0, -int(self._scroll_offset))
            if draw_rect.colliderect(self.list_rect) and button.enabled and draw_rect.collidepoint(
                click_pos
            ):
                self.game.start_level(int(button.value))
                return

    def update(self, dt: float) -> None:
        self.fade_alpha = max(0.0, self.fade_alpha - dt * 500.0)

    def render(self, surface: pygame.Surface) -> None:
        self._draw_background(surface)
        title = self.title_font.render("레벨 선택", True, (238, 238, 244))
        surface.blit(title, title.get_rect(center=(480, 68)))

        hover_pos = self.game.window_to_base(pygame.mouse.get_pos())
        previous_clip = surface.get_clip()
        surface.set_clip(self.list_rect)
        for button in self.level_buttons:
            draw_rect = button.rect.move(0, -int(self._scroll_offset))
            if not draw_rect.colliderect(self.list_rect):
                continue
            draw_button(
                surface,
                self.button_font,
                UIButton(rect=draw_rect, label=button.label, value=button.value, enabled=button.enabled),
                hover_pos is not None and draw_rect.collidepoint(hover_pos),
            )
            level_idx = int(button.value)
            entry = self.game.level_entries[level_idx]
            best = self.game.save_data.get("best_records", {}).get(entry.level_id)
            if isinstance(best, dict):
                record_text = (
                    f"BEST 클릭 {int(best.get('clicks', 0))} / "
                    f"{float(best.get('time_sec', 0.0)):.2f}s"
                )
                record_surf = self.info_font.render(record_text, True, (183, 194, 220))
                record_rect = record_surf.get_rect(midright=(draw_rect.right - 16, draw_rect.centery))
                surface.blit(record_surf, record_rect)
        surface.set_clip(previous_clip)

        if self._max_scroll > 0.0:
            scroll_ratio = self._scroll_offset / max(1.0, self._max_scroll)
            track = pygame.Rect(self.list_rect.right + 8, self.list_rect.top, 8, self.list_rect.height)
            thumb_h = max(36, int(self.list_rect.height * (self.list_rect.height / (self.list_rect.height + self._max_scroll))))
            thumb_y = track.top + int((track.height - thumb_h) * scroll_ratio)
            pygame.draw.rect(surface, (48, 60, 86), track, border_radius=4)
            pygame.draw.rect(surface, (112, 136, 182), pygame.Rect(track.x, thumb_y, track.width, thumb_h), border_radius=4)

        back_hover = hover_pos is not None and self.back_button.rect.collidepoint(hover_pos)
        draw_button(surface, self.button_font, self.back_button, back_hover)

        hint = self.info_font.render("클릭/터치 시작 | 휠/↑↓ 스크롤", True, (185, 198, 228))
        surface.blit(hint, hint.get_rect(midright=(930, 498)))

        if self.fade_alpha > 0:
            overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, int(self.fade_alpha)))
            surface.blit(overlay, (0, 0))

    @staticmethod
    def _draw_background(surface: pygame.Surface) -> None:
        for y in range(surface.get_height()):
            t = y / max(1, surface.get_height() - 1)
            color = (12 + int(12 * t), 19 + int(18 * t), 28 + int(26 * t))
            pygame.draw.line(surface, color, (0, y), (surface.get_width(), y))
        pygame.draw.rect(surface, (26, 34, 48), pygame.Rect(90, 118, 780, 372), border_radius=12)
        pygame.draw.rect(surface, (43, 57, 82), pygame.Rect(90, 118, 780, 372), width=2, border_radius=12)
