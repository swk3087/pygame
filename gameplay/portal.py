from __future__ import annotations

from dataclasses import dataclass

import pygame

from core.config import PORTAL_COOLDOWN_SEC
from gameplay.tilemap import PortalNode


@dataclass(slots=True)
class TeleportResult:
    destination_center: tuple[int, int]
    source_id: int
    destination_id: int


class PortalSystem:
    def __init__(self, tile_size: int, portal_groups: dict[int, list[PortalNode]]) -> None:
        self.tile_size = tile_size
        self.portal_groups = portal_groups
        self.cooldown_sec = PORTAL_COOLDOWN_SEC
        self._last_teleport_time = -9999.0
        self._blocked_rect: pygame.Rect | None = None

    def try_teleport(
        self,
        player_rect: pygame.Rect,
        now_sec: float,
    ) -> TeleportResult | None:
        if self._blocked_rect and not self._blocked_rect.colliderect(player_rect):
            self._blocked_rect = None

        if now_sec - self._last_teleport_time < self.cooldown_sec:
            return None

        source_node = self._find_current_node(player_rect)
        if source_node is None:
            return None
        if self._blocked_rect and self._blocked_rect.colliderect(player_rect):
            return None

        group = self.portal_groups.get(source_node.portal_id, [])
        if len(group) < 2:
            return None
        destination_index = (group.index(source_node) + 1) % len(group)
        destination_node = group[destination_index]
        destination_rect = destination_node.rect(self.tile_size)

        self._last_teleport_time = now_sec
        self._blocked_rect = destination_rect.copy()
        return TeleportResult(
            destination_center=destination_node.center(self.tile_size),
            source_id=source_node.portal_id,
            destination_id=destination_node.portal_id,
        )

    def _find_current_node(self, player_rect: pygame.Rect) -> PortalNode | None:
        for group_nodes in self.portal_groups.values():
            for node in group_nodes:
                if node.rect(self.tile_size).colliderect(player_rect):
                    return node
        return None
