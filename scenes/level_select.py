from __future__ import annotations

from dataclasses import dataclass

import pygame

from core.utils import UIButton, draw_button
from gameplay.tilemap import GOAL, PORTAL, SPIKE, SPAWN, WALL, TileMap


@dataclass(slots=True)
class TabItem:
    key: str
    label: str
    rect: pygame.Rect


class LevelSelectScene:
    def __init__(self, game) -> None:
        self.game = game
        self.fade_alpha = 180.0
        self.list_rect = pygame.Rect(40, 138, 560, 330)
        self.preview_rect = pygame.Rect(620, 138, 300, 330)
        self.search_rect = pygame.Rect(40, 92, 340, 34)
        self.sort_rect = pygame.Rect(392, 92, 208, 34)
        self.back_button = UIButton(
            rect=pygame.Rect(36, 476, 180, 44),
            label="뒤로",
            value="back",
            enabled=True,
        )
        self._scroll_offset = 0.0
        self._max_scroll = 0.0
        self._row_height = 48
        self._row_gap = 8
        self._drag_scrollbar = False
        self._drag_scroll_anchor_y = 0
        self._drag_scroll_start = 0.0
        self._preview_cache: dict[int, TileMap | None] = {}
        self._visible_indices: list[int] = []
        self._selected_level_index: int | None = None
        self._search_text = ""
        self._search_focus = False
        self._filter_key = "all"
        self._sort_mode = "file"
        self._tab_items = [
            TabItem("all", "전체", pygame.Rect(40, 56, 84, 28)),
            TabItem("tutorial", "튜토리얼", pygame.Rect(132, 56, 116, 28)),
            TabItem("mid", "중간", pygame.Rect(256, 56, 84, 28)),
            TabItem("hard", "고난도", pygame.Rect(348, 56, 84, 28)),
        ]
        self._reload_fonts()
        self._rebuild()

    def _reload_fonts(self) -> None:
        self.title_font = self.game.assets.font(42, bold=True)
        self.button_font = self.game.assets.font(22)
        self.row_font = self.game.assets.font(20)
        self.info_font = self.game.assets.font(17)

    def on_settings_changed(self) -> None:
        self._reload_fonts()

    def on_resume(self) -> None:
        self._reload_fonts()
        self._rebuild()

    def _is_unlocked(self, level_index: int) -> bool:
        unlocked = int(self.game.save_data.get("unlocked_level_count", 1))
        return level_index < unlocked

    def _rebuild(self) -> None:
        items = list(self.game.level_entries)
        if self._filter_key != "all":
            items = [entry for entry in items if entry.difficulty == self._filter_key]
        if self._search_text:
            q = self._search_text.lower()
            items = [
                entry
                for entry in items
                if q in entry.name.lower() or q in entry.level_id.lower() or q in entry.path.name.lower()
            ]
        if self._sort_mode == "name":
            items.sort(key=lambda e: (e.name.lower(), e.path.name.lower()))
        else:
            items.sort(key=lambda e: e.path.name.lower())
        self._visible_indices = [entry.index for entry in items]
        self._refresh_scroll_limits()
        if self._selected_level_index not in self._visible_indices:
            self._selected_level_index = self._visible_indices[0] if self._visible_indices else None

    def _refresh_scroll_limits(self) -> None:
        count = len(self._visible_indices)
        if count <= 0:
            self._max_scroll = 0.0
            self._scroll_offset = 0.0
            return
        content_h = count * (self._row_height + self._row_gap) - self._row_gap
        self._max_scroll = max(0.0, float(content_h - self.list_rect.height))
        self._scroll_offset = max(0.0, min(self._scroll_offset, self._max_scroll))

    def _scroll_by(self, delta: float) -> None:
        if self._max_scroll <= 0.0:
            return
        self._scroll_offset = max(0.0, min(self._max_scroll, self._scroll_offset + delta))

    def _scroll_track_rect(self) -> pygame.Rect:
        return pygame.Rect(self.list_rect.right + 6, self.list_rect.top, 10, self.list_rect.height)

    def _scroll_thumb_rect(self) -> pygame.Rect | None:
        if self._max_scroll <= 0.0:
            return None
        track = self._scroll_track_rect()
        visible_ratio = self.list_rect.height / (self.list_rect.height + self._max_scroll)
        thumb_h = max(28, int(track.height * visible_ratio))
        ratio = self._scroll_offset / max(1.0, self._max_scroll)
        thumb_y = track.top + int((track.height - thumb_h) * ratio)
        return pygame.Rect(track.x, thumb_y, track.width, thumb_h)

    def _difficulty_label(self, difficulty: str) -> str:
        if difficulty == "tutorial":
            return "튜토리얼"
        if difficulty == "hard":
            return "고난도"
        return "중간"

    def _difficulty_color(self, difficulty: str) -> tuple[int, int, int]:
        if difficulty == "tutorial":
            return (122, 206, 142)
        if difficulty == "hard":
            return (232, 120, 120)
        return (120, 172, 232)

    def _resolve_click_row(self, click_pos: tuple[int, int]) -> int | None:
        if not self.list_rect.collidepoint(click_pos):
            return None
        local_y = click_pos[1] - self.list_rect.top + int(self._scroll_offset)
        row_block = self._row_height + self._row_gap
        if row_block <= 0:
            return None
        idx_in_visible = local_y // row_block
        if idx_in_visible < 0 or idx_in_visible >= len(self._visible_indices):
            return None
        row_y = idx_in_visible * row_block
        if local_y > row_y + self._row_height:
            return None
        return self._visible_indices[int(idx_in_visible)]

    def _start_selected_if_playable(self) -> None:
        if self._selected_level_index is None:
            return
        entry = self.game.level_entries[self._selected_level_index]
        if self._is_unlocked(entry.index) and entry.valid:
            self.game.start_level(entry.index)

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
            if event.key == pygame.K_RETURN:
                self._start_selected_if_playable()
                return
            if event.key == pygame.K_BACKSPACE and self._search_focus:
                self._search_text = self._search_text[:-1]
                self._rebuild()
                return
            if event.key == pygame.K_TAB:
                tab_keys = [tab.key for tab in self._tab_items]
                cur = tab_keys.index(self._filter_key)
                self._filter_key = tab_keys[(cur + 1) % len(tab_keys)]
                self._rebuild()
                return

        if event.type == pygame.TEXTINPUT and self._search_focus:
            if len(self._search_text) < 32:
                self._search_text += event.text
                self._rebuild()
            return

        if event.type == pygame.MOUSEWHEEL:
            self._scroll_by(-event.y * 36)
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button in {4, 5}:
            self._scroll_by(-36 if event.button == 4 else 36)
            return

        click_pos = None
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            click_pos = self.game.window_to_base(event.pos)
        elif event.type == pygame.FINGERDOWN:
            click_pos = self.game.finger_to_base(event.x, event.y)

        if click_pos is not None:
            if self.back_button.rect.collidepoint(click_pos):
                self.game.open_main_menu()
                return

            self._search_focus = self.search_rect.collidepoint(click_pos)

            for tab in self._tab_items:
                if tab.rect.collidepoint(click_pos):
                    self._filter_key = tab.key
                    self._rebuild()
                    return

            if self.sort_rect.collidepoint(click_pos):
                self._sort_mode = "name" if self._sort_mode == "file" else "file"
                self._rebuild()
                return

            thumb = self._scroll_thumb_rect()
            if thumb is not None and thumb.collidepoint(click_pos):
                self._drag_scrollbar = True
                self._drag_scroll_anchor_y = click_pos[1]
                self._drag_scroll_start = self._scroll_offset
                return

            resolved = self._resolve_click_row(click_pos)
            if resolved is not None:
                self._selected_level_index = resolved
                entry = self.game.level_entries[resolved]
                if self._is_unlocked(entry.index) and entry.valid:
                    self.game.start_level(resolved)
                return

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._drag_scrollbar = False
            return

        if event.type == pygame.MOUSEMOTION and self._drag_scrollbar:
            mouse_base = self.game.window_to_base(event.pos)
            if mouse_base is None:
                return
            track = self._scroll_track_rect()
            thumb = self._scroll_thumb_rect()
            if thumb is None:
                return
            movable = max(1, track.height - thumb.height)
            dy = mouse_base[1] - self._drag_scroll_anchor_y
            self._scroll_offset = max(
                0.0,
                min(self._max_scroll, self._drag_scroll_start + (dy / movable) * self._max_scroll),
            )

    def _draw_row(self, surface: pygame.Surface, row_rect: pygame.Rect, level_index: int) -> None:
        entry = self.game.level_entries[level_index]
        unlocked = self._is_unlocked(level_index)
        selected = self._selected_level_index == level_index
        hover_pos = self.game.window_to_base(pygame.mouse.get_pos())
        hovered = hover_pos is not None and row_rect.collidepoint(hover_pos)

        if not unlocked:
            bg = (64, 64, 72)
            fg = (150, 150, 162)
        elif not entry.valid:
            bg = (96, 58, 58)
            fg = (236, 194, 194)
        elif selected:
            bg = (92, 118, 170)
            fg = (246, 246, 250)
        elif hovered:
            bg = (75, 98, 148)
            fg = (238, 238, 244)
        else:
            bg = (56, 70, 104)
            fg = (230, 230, 236)

        pygame.draw.rect(surface, bg, row_rect, border_radius=8)
        pygame.draw.rect(surface, (20, 24, 32), row_rect, width=2, border_radius=8)

        label = f"{entry.index + 1:03d}. {entry.name}"
        if not unlocked:
            label += " (잠김)"
        elif not entry.valid:
            label += " (오류)"
        txt = self.row_font.render(label, True, fg)
        surface.blit(txt, txt.get_rect(midleft=(row_rect.left + 12, row_rect.centery)))

        diff_color = self._difficulty_color(entry.difficulty)
        diff_text = self.row_font.render(self._difficulty_label(entry.difficulty), True, diff_color)
        surface.blit(diff_text, diff_text.get_rect(midright=(row_rect.right - 10, row_rect.centery)))

    def _get_preview_tilemap(self, level_index: int) -> TileMap | None:
        if level_index in self._preview_cache:
            return self._preview_cache[level_index]
        entry = self.game.level_entries[level_index]
        if not entry.valid:
            self._preview_cache[level_index] = None
            return None
        try:
            tilemap = TileMap.from_json(entry.path)
        except Exception:
            self._preview_cache[level_index] = None
            return None
        self._preview_cache[level_index] = tilemap
        return tilemap

    def _draw_preview_map(self, surface: pygame.Surface, rect: pygame.Rect, level_index: int) -> None:
        tilemap = self._get_preview_tilemap(level_index)
        if tilemap is None:
            msg = self.info_font.render("미리보기 불가", True, (210, 170, 170))
            surface.blit(msg, msg.get_rect(center=rect.center))
            return

        scale = min(rect.width / tilemap.width, rect.height / tilemap.height)
        draw_w = max(1, int(tilemap.width * scale))
        draw_h = max(1, int(tilemap.height * scale))
        ox = rect.left + (rect.width - draw_w) // 2
        oy = rect.top + (rect.height - draw_h) // 2
        tile_px = max(1, int(scale))
        color_map = {
            WALL: (88, 98, 120),
            SPAWN: (110, 132, 170),
            GOAL: (110, 198, 120),
            SPIKE: (188, 96, 96),
            PORTAL: (92, 196, 198),
        }
        for ty in range(tilemap.height):
            for tx in range(tilemap.width):
                tile_type = tilemap.tile_types[ty][tx]
                if tile_type not in color_map:
                    continue
                r = pygame.Rect(ox + tx * tile_px, oy + ty * tile_px, tile_px, tile_px)
                pygame.draw.rect(surface, color_map[tile_type], r)
        pygame.draw.rect(surface, (30, 34, 44), rect, width=1)

    def update(self, dt: float) -> None:
        self.fade_alpha = max(0.0, self.fade_alpha - dt * 500.0)

    def render(self, surface: pygame.Surface) -> None:
        self._draw_background(surface)
        title = self.title_font.render("레벨 브라우저", True, (238, 238, 244))
        surface.blit(title, title.get_rect(midleft=(42, 28)))

        mouse_pos = self.game.window_to_base(pygame.mouse.get_pos())
        for tab in self._tab_items:
            active = tab.key == self._filter_key
            hovered = mouse_pos is not None and tab.rect.collidepoint(mouse_pos)
            bg = (110, 128, 176) if active else ((76, 95, 140) if hovered else (56, 72, 106))
            pygame.draw.rect(surface, bg, tab.rect, border_radius=6)
            pygame.draw.rect(surface, (20, 24, 32), tab.rect, width=2, border_radius=6)
            text = self.info_font.render(tab.label, True, (236, 236, 242))
            surface.blit(text, text.get_rect(center=tab.rect.center))

        search_bg = (78, 100, 144) if self._search_focus else (56, 72, 106)
        pygame.draw.rect(surface, search_bg, self.search_rect, border_radius=6)
        pygame.draw.rect(surface, (20, 24, 32), self.search_rect, width=2, border_radius=6)
        search_text = self._search_text if self._search_text else "검색 (이름/id)"
        search_color = (236, 236, 242) if self._search_text else (168, 176, 196)
        search_surf = self.info_font.render(search_text, True, search_color)
        surface.blit(search_surf, search_surf.get_rect(midleft=(self.search_rect.left + 10, self.search_rect.centery)))

        sort_label = "정렬: 파일순" if self._sort_mode == "file" else "정렬: 이름순"
        pygame.draw.rect(surface, (56, 72, 106), self.sort_rect, border_radius=6)
        pygame.draw.rect(surface, (20, 24, 32), self.sort_rect, width=2, border_radius=6)
        sort_surf = self.info_font.render(sort_label, True, (236, 236, 242))
        surface.blit(sort_surf, sort_surf.get_rect(center=self.sort_rect.center))

        pygame.draw.rect(surface, (28, 34, 52), self.list_rect, border_radius=10)
        pygame.draw.rect(surface, (41, 52, 78), self.list_rect, width=2, border_radius=10)
        previous_clip = surface.get_clip()
        surface.set_clip(self.list_rect)
        row_step = self._row_height + self._row_gap
        for visible_idx, level_index in enumerate(self._visible_indices):
            row_y = self.list_rect.top + visible_idx * row_step - int(self._scroll_offset)
            row_rect = pygame.Rect(self.list_rect.left + 8, row_y, self.list_rect.width - 16, self._row_height)
            if row_rect.bottom < self.list_rect.top or row_rect.top > self.list_rect.bottom:
                continue
            self._draw_row(surface, row_rect, level_index)
        surface.set_clip(previous_clip)

        thumb = self._scroll_thumb_rect()
        if thumb is not None:
            track = self._scroll_track_rect()
            pygame.draw.rect(surface, (48, 60, 86), track, border_radius=4)
            pygame.draw.rect(surface, (122, 144, 194), thumb, border_radius=4)

        pygame.draw.rect(surface, (28, 34, 52), self.preview_rect, border_radius=10)
        pygame.draw.rect(surface, (41, 52, 78), self.preview_rect, width=2, border_radius=10)
        self._draw_preview_panel(surface)

        back_hover = mouse_pos is not None and self.back_button.rect.collidepoint(mouse_pos)
        draw_button(
            surface,
            self.button_font,
            self.back_button,
            back_hover,
            high_contrast=bool(self.game.settings.get("high_contrast_ui", False)),
        )

        hint = self.info_font.render("휠/↑↓/PgUp/PgDn 스크롤 | Enter 시작", True, (185, 198, 228))
        surface.blit(hint, hint.get_rect(midright=(930, 496)))

        if self.fade_alpha > 0:
            overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, int(self.fade_alpha)))
            surface.blit(overlay, (0, 0))

    def _draw_preview_panel(self, surface: pygame.Surface) -> None:
        if self._selected_level_index is None:
            text = self.info_font.render("표시할 레벨이 없습니다.", True, (198, 198, 210))
            surface.blit(text, text.get_rect(center=self.preview_rect.center))
            return

        entry = self.game.level_entries[self._selected_level_index]
        unlocked = self._is_unlocked(entry.index)

        title = self.row_font.render(entry.name, True, (238, 238, 244))
        surface.blit(title, title.get_rect(midleft=(self.preview_rect.left + 12, self.preview_rect.top + 20)))
        meta = self.info_font.render(
            f"{entry.level_id} | {self._difficulty_label(entry.difficulty)}", True, (184, 200, 232)
        )
        surface.blit(meta, meta.get_rect(midleft=(self.preview_rect.left + 12, self.preview_rect.top + 44)))

        if not unlocked:
            status = "잠김"
            status_color = (210, 162, 162)
        elif not entry.valid:
            status = "오류"
            status_color = (232, 142, 142)
        else:
            status = "플레이 가능"
            status_color = (142, 220, 164)
        status_surf = self.info_font.render(f"상태: {status}", True, status_color)
        surface.blit(status_surf, status_surf.get_rect(midleft=(self.preview_rect.left + 12, self.preview_rect.top + 68)))

        stats = self.info_font.render(
            f"크기 {entry.size_text} | 가시 {entry.spike_count} | 포탈그룹 {entry.portal_group_count}",
            True,
            (190, 198, 214),
        )
        surface.blit(stats, stats.get_rect(midleft=(self.preview_rect.left + 12, self.preview_rect.top + 90)))

        if entry.issue:
            issue = self.info_font.render(f"오류: {entry.issue[:30]}", True, (226, 152, 152))
            surface.blit(
                issue, issue.get_rect(midleft=(self.preview_rect.left + 12, self.preview_rect.top + 112))
            )

        mini = pygame.Rect(self.preview_rect.left + 12, self.preview_rect.top + 136, 276, 178)
        pygame.draw.rect(surface, (18, 24, 34), mini, border_radius=6)
        self._draw_preview_map(surface, mini.inflate(-4, -4), self._selected_level_index)

    @staticmethod
    def _draw_background(surface: pygame.Surface) -> None:
        for y in range(surface.get_height()):
            t = y / max(1, surface.get_height() - 1)
            color = (12 + int(12 * t), 19 + int(18 * t), 28 + int(26 * t))
            pygame.draw.line(surface, color, (0, y), (surface.get_width(), y))
