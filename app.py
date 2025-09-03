from __future__ import annotations
import sys
import math
import pygame as pg

import settings as S
from engine.iso import grid_to_screen, screen_to_grid, diamond_points, tile_center
from engine import colors as C
from engine.map import TileMap
from engine.pathfinding import a_star
from engine.unit import Unit
from engine.turns import TurnManager, Phase


def draw_grid(surface: pg.Surface) -> None:
    for j in range(S.GRID_ROWS):
        for i in range(S.GRID_COLS):
            sx, sy = grid_to_screen(i, j, S.TILE_W, S.TILE_H, S.ORIGIN)
            poly = diamond_points(sx, sy, S.TILE_W, S.TILE_H)
            fill = C.GRID_A if (i + j) % 2 == 0 else C.GRID_B
            pg.draw.polygon(surface, fill, poly)
            pg.draw.polygon(surface, C.OUTLINE, poly, width=1)


def draw_obstacles(surface: pg.Surface, tmap: TileMap) -> None:
    for (i, j) in tmap.blocked:
        sx, sy = grid_to_screen(i, j, S.TILE_W, S.TILE_H, S.ORIGIN)
        poly = diamond_points(sx, sy, S.TILE_W, S.TILE_H)
        pg.draw.polygon(surface, C.OBSTACLE_FILL, poly)
        pg.draw.polygon(surface, C.OBSTACLE_OUTLINE, poly, width=2)


def draw_hover(surface: pg.Surface, mouse_pos: tuple[int, int]) -> tuple[int, int] | None:
    mx, my = mouse_pos
    i, j = screen_to_grid(mx, my, S.TILE_W, S.TILE_H, S.ORIGIN)
    if 0 <= i < S.GRID_COLS and 0 <= j < S.GRID_ROWS:
        sx, sy = grid_to_screen(i, j, S.TILE_W, S.TILE_H, S.ORIGIN)
        poly = diamond_points(sx, sy, S.TILE_W, S.TILE_H)
        pg.draw.polygon(surface, C.HOVER_FILL, poly)
        pg.draw.polygon(surface, C.HOVER_OUTLINE, poly, width=2)
        return (i, j)
    return None


def draw_selection(surface: pg.Surface, selected: tuple[int, int] | None) -> None:
    if not selected:
        return
    i, j = selected
    sx, sy = grid_to_screen(i, j, S.TILE_W, S.TILE_H, S.ORIGIN)
    poly = diamond_points(sx, sy, S.TILE_W, S.TILE_H)
    pg.draw.polygon(surface, C.SELECT_FILL, poly)
    pg.draw.polygon(surface, C.SELECT_OUTLINE, poly, width=2)


def bfs_reachable(origin: tuple[int, int], max_steps: int, tmap: TileMap) -> set[tuple[int, int]]:
    from collections import deque
    frontier = deque()
    frontier.append((origin, 0))
    visited = {origin}
    reachable: set[tuple[int, int]] = set()

    while frontier:
        (ci, cj), d = frontier.popleft()
        if d == max_steps:
            continue
        for (ni, nj) in ((ci+1,cj), (ci-1,cj), (ci,cj+1), (ci,cj-1)):
            nc = (ni, nj)
            if not tmap.in_bounds(nc) or not tmap.passable(nc) or nc in visited:
                continue
            visited.add(nc)
            reachable.add(nc)
            frontier.append((nc, d + 1))
    return reachable


def draw_move_ranges(surface: pg.Surface, origin: tuple[int, int] | None, tmap: TileMap, available_ap: int) -> None:
    if not origin or available_ap <= 0:
        return

    overlay = pg.Surface(surface.get_size(), pg.SRCALPHA)

    # Blue (1 AP)
    blue = bfs_reachable(origin, S.MOVEMENT_TILES_PER_AP, tmap)
    for (i, j) in blue:
        sx, sy = grid_to_screen(i, j, S.TILE_W, S.TILE_H, S.ORIGIN)
        poly = diamond_points(sx, sy, S.TILE_W, S.TILE_H)
        pg.draw.polygon(overlay, C.MOVE_BLUE_FILL, poly)
        pg.draw.polygon(overlay, C.MOVE_BLUE_OUTLINE, poly, width=1)

    # Yellow (2 AP) only if we have 2 AP to spend
    if available_ap >= 2:
        yellow = bfs_reachable(origin, S.MOVEMENT_TILES_PER_AP * 2, tmap) - blue
        for (i, j) in yellow:
            sx, sy = grid_to_screen(i, j, S.TILE_W, S.TILE_H, S.ORIGIN)
            poly = diamond_points(sx, sy, S.TILE_W, S.TILE_H)
            pg.draw.polygon(overlay, C.MOVE_YELLOW_FILL, poly)
            pg.draw.polygon(overlay, C.MOVE_YELLOW_OUTLINE, poly, width=1)

    surface.blit(overlay, (0, 0))


def draw_path_preview(surface: pg.Surface, origin: tuple[int, int] | None, hovered: tuple[int, int] | None, tmap: TileMap) -> tuple[int, int] | None:
    if not origin or not hovered:
        return None
    if not tmap.passable(hovered):
        return None

    path = a_star(origin, hovered, S.GRID_COLS, S.GRID_ROWS, tmap.blocked)
    if not path:
        return None

    max_steps = S.MOVEMENT_TILES_PER_AP * 2
    path = path[:max_steps]

    overlay = pg.Surface(surface.get_size(), pg.SRCALPHA)
    for (i, j) in path:
        sx, sy = grid_to_screen(i, j, S.TILE_W, S.TILE_H, S.ORIGIN)
        poly = diamond_points(sx, sy, S.TILE_W, S.TILE_H)
        pg.draw.polygon(overlay, C.PATH_FILL, poly)
        pg.draw.polygon(overlay, C.PATH_OUTLINE, poly, width=1)
    surface.blit(overlay, (0, 0))

    steps = len(path)
    ap_cost = math.ceil(steps / S.MOVEMENT_TILES_PER_AP) if steps > 0 else 0
    return steps, ap_cost


def draw_unit(surface: pg.Surface, u: Unit) -> None:
    r = max(6, S.TILE_H // 3)
    pg.draw.circle(surface, C.UNIT_FILL, (int(u.pos_x), int(u.pos_y)), r)
    pg.draw.circle(surface, C.UNIT_OUTLINE, (int(u.pos_x), int(u.pos_y)), r, width=2)


def draw_debug(surface: pg.Surface, font: pg.font.Font, hovered: tuple[int, int] | None, unit: Unit, path_info: tuple[int, int] | None, tm: TurnManager) -> None:
    phase_txt = "PLAYER" if tm.phase is Phase.PLAYER else "ENEMY"
    lines = [
        f"Turn: {tm.turn}   Phase: {phase_txt}",
        f"Hovered: {hovered}" if hovered is not None else "Hovered: None",
        f"Unit@grid: {unit.grid}  AP: {unit.ap}/{unit.ap_max}",
        f"Origin: {S.ORIGIN}  Tile: {S.TILE_W}x{S.TILE_H}  Grid: {S.GRID_COLS}x{S.GRID_ROWS}",
        f"1 AP tiles: {S.MOVEMENT_TILES_PER_AP} (dash=2x)",
        "ENTER/E: end turn   L-Click: move (if enough AP & player phase)   B: toggle obstacle   R: refill AP   ESC: quit",
    ]
    if path_info is not None:
        steps, ap_cost = path_info
        lines.insert(3, f"Path steps: {steps}   AP cost: {ap_cost}")

    x, y = 10, 10
    for text in lines:
        surf = font.render(text, True, C.TEXT)
        surface.blit(surf, (x, y))
        y += surf.get_height() + 2


def main() -> int:
    pg.init()
    try:
        screen = pg.display.set_mode((S.WINDOW_W, S.WINDOW_H))
        pg.display.set_caption("XCOM Iso — Turn Scaffold")
        clock = pg.time.Clock()
        font = pg.font.SysFont("consolas", 16)

        tmap = TileMap(S.GRID_COLS, S.GRID_ROWS)
        unit = Unit(S.UNIT_SPAWN, S.TILE_W, S.TILE_H, S.ORIGIN, S.MOVE_SPEED_PPS)
        tm = TurnManager()

        running = True
        pending_dest: tuple[int, int] | None = None

        while running:
            dt = clock.tick(S.FPS) / 1000.0  # seconds

            for e in pg.event.get():
                if e.type == pg.QUIT:
                    running = False
                elif e.type == pg.KEYDOWN:
                    if e.key == pg.K_ESCAPE:
                        running = False
                    elif e.key == pg.K_b and tm.phase is Phase.PLAYER:
                        hov = screen_to_grid(*pg.mouse.get_pos(), S.TILE_W, S.TILE_H, S.ORIGIN)
                        if tmap.in_bounds(hov) and hov != unit.grid:
                            tmap.toggle_block(hov)
                    elif e.key == pg.K_r and tm.phase is Phase.PLAYER:
                        unit.ap = unit.ap_max
                    elif e.key in (pg.K_RETURN, pg.K_e):
                        if tm.phase is Phase.PLAYER and not unit.is_moving():
                            tm.end_player_turn()
                elif e.type == pg.MOUSEBUTTONDOWN and e.button == 1 and tm.phase is Phase.PLAYER:
                    i, j = screen_to_grid(*e.pos, S.TILE_W, S.TILE_H, S.ORIGIN)
                    target = (i, j)
                    if tmap.in_bounds(target) and tmap.passable(target):
                        path = a_star(unit.grid, target, S.GRID_COLS, S.GRID_ROWS, tmap.blocked)
                        if path:
                            steps = len(path)
                            ap_cost = math.ceil(steps / S.MOVEMENT_TILES_PER_AP)
                            if unit.can_afford(ap_cost):
                                unit.set_path(path, ap_cost)
                                pending_dest = target

            # Update unit
            before = unit.is_moving()
            unit.update(dt)
            after = unit.is_moving()
            if before and not after and pending_dest is not None:
                unit.set_grid_immediate(pending_dest)
                pending_dest = None

            # Update turn manager
            started_player_turn = tm.update(dt)
            if started_player_turn:
                unit.ap = unit.ap_max  # refresh AP at start of each player turn

            # Draw
            screen.fill(C.BG)
            draw_grid(screen)
            draw_obstacles(screen, tmap)
            draw_move_ranges(screen, unit.grid, tmap, unit.ap if tm.phase is Phase.PLAYER else 0)
            hovered = draw_hover(screen, pg.mouse.get_pos())
            path_info = draw_path_preview(screen, unit.grid, hovered, tmap) if tm.phase is Phase.PLAYER else None
            draw_unit(screen, unit)
            draw_debug(screen, font, hovered, unit, path_info, tm)

            pg.display.flip()

        return 0
    finally:
        pg.quit()


if __name__ == "__main__":
    sys.exit(main())
