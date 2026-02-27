from __future__ import annotations

from pathlib import Path

import pygame


class AssetManager:
    def __init__(self, asset_root: Path) -> None:
        self.asset_root = asset_root
        self._font_cache: dict[tuple[int, bool], pygame.font.Font] = {}
        self._font_path = self._pick_project_font_path()
        self._font_name = self._pick_ui_font_name() if self._font_path is None else ""
        self._font_source = (
            f"project:{self._font_path.name}" if self._font_path is not None else f"system:{self._font_name}"
        )
        self._ui_scale_percent = 100
        self.master_volume = 0.7
        self._mixer_ready = False
        self._sounds: dict[str, pygame.mixer.Sound] = {}
        self._setup_audio()
        self._load_optional_sounds()

    def font_source(self) -> str:
        return self._font_source

    def set_ui_scale(self, ui_scale_percent: int) -> None:
        safe_scale = max(50, min(200, int(ui_scale_percent)))
        if safe_scale == self._ui_scale_percent:
            return
        self._ui_scale_percent = safe_scale
        self._font_cache.clear()

    def _scaled_size(self, size: int) -> int:
        return max(8, int(round(size * self._ui_scale_percent / 100.0)))

    def _pick_project_font_path(self) -> Path | None:
        fonts_dir = self.asset_root / "fonts"
        if not fonts_dir.exists():
            return None
        candidates = sorted(
            [
                path
                for path in fonts_dir.iterdir()
                if path.is_file() and path.suffix.lower() in {".ttf", ".otf", ".ttc"}
            ],
            key=lambda p: p.name.lower(),
        )
        if not candidates:
            return None
        preferred_names = ("notosanskr", "nanum", "malgun", "gothic", "korean", "kr")
        for path in candidates:
            lowered = path.name.lower().replace(" ", "")
            if any(token in lowered for token in preferred_names):
                return path
        return candidates[0]

    @staticmethod
    def _pick_ui_font_name() -> str:
        available = set(pygame.font.get_fonts())
        # Korean-capable fonts first to prevent broken Hangul glyphs.
        preferred = [
            "malgungothic",
            "nanumgothic",
            "notosanskr",
            "dotum",
            "gulim",
            "batang",
            "segoeuisemibold",
            "arial",
            "sans",
        ]
        for name in preferred:
            if name.replace(" ", "") in available:
                return name
        return "sans"

    def _setup_audio(self) -> None:
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            self._mixer_ready = True
        except pygame.error:
            self._mixer_ready = False

    def _load_optional_sounds(self) -> None:
        if not self._mixer_ready:
            return
        sound_files = {
            "rotate": self.asset_root / "sfx" / "rotate.wav",
            "teleport": self.asset_root / "sfx" / "teleport.wav",
            "clear": self.asset_root / "sfx" / "clear.wav",
        }
        for key, path in sound_files.items():
            if not path.exists():
                continue
            try:
                self._sounds[key] = pygame.mixer.Sound(str(path))
            except pygame.error:
                continue
        self.set_master_volume(int(self.master_volume * 100))

    def font(self, size: int, bold: bool = False) -> pygame.font.Font:
        scaled_size = self._scaled_size(size)
        key = (scaled_size, bold)
        if key in self._font_cache:
            return self._font_cache[key]
        font: pygame.font.Font
        if self._font_path is not None:
            try:
                font = pygame.font.Font(str(self._font_path), scaled_size)
                font.set_bold(bold)
            except (OSError, pygame.error):
                self._font_path = None
                self._font_name = self._pick_ui_font_name()
                self._font_source = f"system:{self._font_name}"
                font = pygame.font.SysFont(self._font_name, scaled_size, bold=bold)
        else:
            try:
                font = pygame.font.SysFont(self._font_name, scaled_size, bold=bold)
            except pygame.error:
                font = pygame.font.Font(None, scaled_size)
                font.set_bold(bold)
        self._font_cache[key] = font
        return font

    def set_master_volume(self, value_0_100: int) -> None:
        self.master_volume = max(0.0, min(1.0, value_0_100 / 100.0))
        for sound in self._sounds.values():
            sound.set_volume(self.master_volume)

    def play(self, sound_name: str) -> None:
        sound = self._sounds.get(sound_name)
        if sound is None:
            return
        sound.play()
