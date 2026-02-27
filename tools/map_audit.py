from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import pygame
except ModuleNotFoundError:
    pygame = None

if pygame is not None:
    from core.config import ROTATE_COOLDOWN_SEC
    from gameplay.player import Player
    from gameplay.portal import PortalSystem
    from gameplay.tilemap import GOAL, SPAWN, MapValidationError, TileMap

    GRAVITY_DIRS = [
        pygame.Vector2(0.0, 1.0),
        pygame.Vector2(-1.0, 0.0),
        pygame.Vector2(0.0, -1.0),
        pygame.Vector2(1.0, 0.0),
    ]
else:
    ROTATE_COOLDOWN_SEC = 0.06
    GOAL = "GOAL"
    SPAWN = "SPAWN"
    GRAVITY_DIRS: list[Any] = []


VALID_TILE_TYPES = {"EMPTY", "WALL", "SPAWN", "GOAL", "SPIKE"}


@dataclass(slots=True)
class AuditResult:
    path: Path
    ok: bool
    errors: list[str]
    warnings: list[str]


def _load_raw_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("JSON 루트는 객체여야 합니다.")
    return data


def _count_tile_type(raw: dict[str, Any], wanted_type: str) -> int:
    legend = raw.get("legend", {})
    grid = raw.get("grid", [])
    if not isinstance(legend, dict) or not isinstance(grid, list):
        return 0
    mapped_chars = {ch for ch, tile_type in legend.items() if tile_type == wanted_type}
    count = 0
    for row in grid:
        if not isinstance(row, str):
            continue
        for ch in row:
            if ch in mapped_chars:
                count += 1
    return count


def _validate_legend_value(value: Any) -> str | None:
    if not isinstance(value, str):
        return "legend 값은 문자열이어야 함"
    value = value.strip().upper()
    if value in VALID_TILE_TYPES:
        return None
    if value.startswith("PORTAL:"):
        _, _, tail = value.partition(":")
        try:
            portal_id = int(tail)
        except ValueError:
            return f"포탈 id 정수 변환 실패: {value}"
        if portal_id < 1:
            return f"포탈 id는 1 이상이어야 함: {value}"
        return None
    return f"알 수 없는 타일 타입: {value}"


def _raw_schema_errors(raw: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    tile_size = raw.get("tile_size")
    width = raw.get("width")
    height = raw.get("height")
    legend = raw.get("legend")
    grid = raw.get("grid")

    if not isinstance(tile_size, int) or tile_size < 1:
        errors.append("tile_size는 1 이상의 정수여야 함")
    if not isinstance(width, int) or width < 1:
        errors.append("width는 1 이상의 정수여야 함")
    if not isinstance(height, int) or height < 1:
        errors.append("height는 1 이상의 정수여야 함")
    if not isinstance(legend, dict):
        errors.append("legend 객체가 필요함")
    if not isinstance(grid, list) or not all(isinstance(row, str) for row in grid):
        errors.append("grid는 문자열 배열이어야 함")
    if errors:
        return errors

    if len(grid) != height:
        errors.append(f"height({height})와 grid 줄 수({len(grid)}) 불일치")
    for i, row in enumerate(grid):
        if len(row) != width:
            errors.append(f"width({width})와 grid[{i}] 길이({len(row)}) 불일치")

    for ch, mapped in legend.items():
        if not isinstance(ch, str) or len(ch) != 1:
            errors.append(f"legend 키는 1글자여야 함: {ch}")
            continue
        err = _validate_legend_value(mapped)
        if err:
            errors.append(f"legend '{ch}': {err}")

    for ty, row in enumerate(grid):
        for tx, ch in enumerate(row):
            if ch not in legend:
                errors.append(f"legend에 없는 문자: '{ch}' at ({tx},{ty})")
    return errors


def _is_goal_reached(tilemap: TileMap, player: Player) -> bool:
    return any(player.rect.colliderect(goal_rect) for goal_rect in tilemap.goal_tiles)


def _run_left_click_simulation(
    tilemap: TileMap,
    click_schedule: list[float],
    max_time_sec: float,
    dt: float = 1.0 / 60.0,
) -> bool:
    player = Player(tilemap.spawn_px, tilemap.tile_size)
    portal_system = PortalSystem(tilemap.tile_size, tilemap.portal_groups)
    gravity_dir = 0
    rotate_cooldown = 0.0
    elapsed = 0.0
    click_idx = 0

    while elapsed <= max_time_sec:
        if _is_goal_reached(tilemap, player):
            return True

        if click_idx < len(click_schedule) and elapsed >= click_schedule[click_idx]:
            if rotate_cooldown <= 0.0:
                gravity_dir = (gravity_dir + 1) % 4
                player.rotate_velocity_ccw()
                player.snap_to_nearest_tile(tilemap)
                rotate_cooldown = ROTATE_COOLDOWN_SEC
            click_idx += 1

        gravity_vec = GRAVITY_DIRS[gravity_dir]
        player.update(dt, gravity_vec, tilemap)
        rotate_cooldown = max(0.0, rotate_cooldown - dt)

        for spike_rect in tilemap.spike_tiles:
            if player.rect.colliderect(spike_rect):
                player.respawn(tilemap.spawn_px)
                break

        tp = portal_system.try_teleport(player.rect, elapsed)
        if tp is not None:
            player.set_center(tp.destination_center)

        elapsed += dt

    return _is_goal_reached(tilemap, player)


def _periodic_schedule(period: float, max_time_sec: float, phase: float) -> list[float]:
    schedule: list[float] = []
    t = phase
    while t <= max_time_sec:
        schedule.append(t)
        t += period
    return schedule


def _random_schedule(rng: random.Random, max_time_sec: float) -> list[float]:
    schedule: list[float] = []
    t = rng.uniform(0.03, 0.35)
    while t <= max_time_sec:
        schedule.append(t)
        t += rng.uniform(0.05, 0.45)
    return schedule


def _left_click_solvable(tilemap: TileMap, max_time_sec: float, random_trials: int) -> bool:
    if _run_left_click_simulation(tilemap, [], max_time_sec):
        return True

    periodic_periods = [0.08, 0.11, 0.14, 0.18, 0.22, 0.28, 0.34, 0.42]
    for period in periodic_periods:
        for phase in (0.01, period * 0.5, period * 0.8):
            schedule = _periodic_schedule(period, max_time_sec, phase)
            if _run_left_click_simulation(tilemap, schedule, max_time_sec):
                return True

    for seed in range(random_trials):
        rng = random.Random(seed)
        schedule = _random_schedule(rng, max_time_sec)
        if _run_left_click_simulation(tilemap, schedule, max_time_sec):
            return True
    return False


def audit_map(path: Path, max_time_sec: float, random_trials: int, check_left_click: bool) -> AuditResult:
    errors: list[str] = []
    warnings: list[str] = []

    try:
        raw = _load_raw_json(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return AuditResult(path=path, ok=False, errors=[f"JSON 로드 실패: {exc}"], warnings=[])

    errors.extend(_raw_schema_errors(raw))

    spawn_count = _count_tile_type(raw, SPAWN)
    if spawn_count != 1:
        errors.append(f"SPAWN 개수는 정확히 1개여야 함 (현재 {spawn_count})")

    goal_count = _count_tile_type(raw, GOAL)
    if goal_count < 1:
        errors.append("GOAL이 최소 1개 필요")

    if pygame is None:
        if check_left_click:
            warnings.append("pygame 미설치: 좌클릭-only 시뮬레이션을 생략함")
        return AuditResult(path=path, ok=len(errors) == 0, errors=errors, warnings=warnings)

    try:
        tilemap = TileMap.from_json(path)
    except MapValidationError as exc:
        errors.append(str(exc))
        tilemap = None

    if tilemap is not None and check_left_click:
        if not _left_click_solvable(tilemap, max_time_sec=max_time_sec, random_trials=random_trials):
            errors.append("좌클릭-only 휴리스틱 검사에서 클리어 경로를 찾지 못함")

    return AuditResult(path=path, ok=len(errors) == 0, errors=errors, warnings=warnings)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="map/*.json 감사 및 좌클릭-only 휴리스틱 검사")
    parser.add_argument("--map-dir", default="map", help="검사할 맵 디렉터리 (기본: map)")
    parser.add_argument("--max-time-sec", type=float, default=12.0, help="시뮬레이션 최대 시간(초)")
    parser.add_argument("--random-trials", type=int, default=120, help="랜덤 탐색 횟수")
    parser.add_argument(
        "--no-left-click-check",
        action="store_true",
        help="좌클릭-only 휴리스틱 검사를 비활성화",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    map_dir = Path(args.map_dir)
    if not map_dir.exists():
        print(f"[FAIL] map 디렉터리가 없습니다: {map_dir}")
        return 1

    if pygame is not None:
        pygame.init()
    else:
        print("[WARN] pygame 미설치 상태: 스키마 검사만 수행합니다.")

    results: list[AuditResult] = []
    for path in sorted(map_dir.glob("*.json"), key=lambda p: p.name.lower()):
        result = audit_map(
            path,
            max_time_sec=float(args.max_time_sec),
            random_trials=max(1, int(args.random_trials)),
            check_left_click=not args.no_left_click_check,
        )
        results.append(result)
        status = "PASS" if result.ok else "FAIL"
        print(f"[{status}] {path.name}")
        for err in result.errors:
            print(f"  - {err}")
        for warn in result.warnings:
            print(f"  - 경고: {warn}")

    if pygame is not None:
        pygame.quit()

    fail_count = sum(1 for r in results if not r.ok)
    print(f"\n총 {len(results)}개 맵 검사, 실패 {fail_count}개")
    return 1 if fail_count > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
