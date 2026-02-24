from __future__ import annotations

from typing import Protocol


class Scene(Protocol):
    def handle_event(self, event) -> None:
        ...

    def update(self, dt: float) -> None:
        ...

    def render(self, surface) -> None:
        ...


class SceneManager:
    def __init__(self) -> None:
        self._stack: list[Scene] = []

    def push(self, scene: Scene) -> None:
        if self._stack:
            self._call(self._stack[-1], "on_pause")
        self._stack.append(scene)
        self._call(scene, "on_enter")

    def pop(self) -> Scene | None:
        if not self._stack:
            return None
        popped = self._stack.pop()
        self._call(popped, "on_exit")
        if self._stack:
            self._call(self._stack[-1], "on_resume")
        return popped

    def replace(self, scene: Scene) -> None:
        if self._stack:
            old = self._stack.pop()
            self._call(old, "on_exit")
        self._stack.append(scene)
        self._call(scene, "on_enter")

    def current_scene(self) -> Scene | None:
        if not self._stack:
            return None
        return self._stack[-1]

    @staticmethod
    def _call(scene: Scene, method_name: str) -> None:
        method = getattr(scene, method_name, None)
        if callable(method):
            method()

