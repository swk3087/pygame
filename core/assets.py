from __future__ import annotations

from pathlib import Path

import pygame


class AssetManager:
    def __init__(self, asset_root: Path) -> None:
        self.asset_root = asset_root
        self._font_cache: dict[tuple[int, bool], pygame.font.Font] = {}
        self._font_name = self._pick_ui_font_name()
        self.master_volume = 0.7
        self._mixer_ready = False
        self._sounds: dict[str, pygame.mixer.Sound] = {}
        self._setup_audio()
        self._load_optional_sounds()

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
        key = (size, bold)
        if key in self._font_cache:
            return self._font_cache[key]
        font = pygame.font.SysFont(self._font_name, size, bold=bold)
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
